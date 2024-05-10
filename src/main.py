import os
from io import StringIO
from time import sleep

import urllib3.exceptions

from kubernetes import client, config, watch
import CloudFlare


def get_loadbalancer_endpoint(service):
    # get the loadbalancer endpoint
    try:
        ingress = service.status.load_balancer.ingress

        if ingress:
            if ingress[0].hostname:
                return str(ingress[0].hostname)
            
        return "N/A"
    except:
        return "N/A"

def get_traefik_endpoint(services):
    for service in services:
        if "traefik" in service.metadata.name:
            return get_loadbalancer_endpoint(service)
    
    return None


def get_ingress_hostnames(ingress):
    if ingress["spec"] and ingress["spec"]["routes"]:
        hosts = []

        for route in ingress["spec"]["routes"]:
            if route["match"] and "Host(" in route["match"]:
                start_idx = route["match"].index("Host(") + 5
                end_idx = route["match"].index(")", start_idx)

                host = route["match"][start_idx:end_idx]

                if host.startswith("`"):
                    host = host[1:]

                if host.endswith("`"):
                    host = host[:-1]

                hosts.append(host)
        
        return hosts or None

    return None

def setup_cname_for_ingress(ingress_hosts, traefik_endpoint):
    # Find if the CNAME already exists via cloudflare API
    # If not, create a new CNAME for the ingress

    print(f"Setting up CNAME for {ingress_hosts} to {traefik_endpoint}")

    cf = CloudFlare.CloudFlare()

    for host in ingress_hosts:
        host_parts = host.split(".")
        zone_name = host_parts[-2] + "." + host_parts[-1]

        zones = cf.zones.get(params={"name": zone_name})
        
        if not zones:
            print(f"Zone {zone_name} not found, skipping")
            continue

        zone = zones[0]

        zone_id = zone["id"]

        dns_records = cf.zones.dns_records.get(zone_id)

        found_record = False

        for record in dns_records:
            if record["name"] == host:
                found_record = True

                if record["type"] == "CNAME":
                    print(f"Found existing CNAME record for {host}")

                    if record["content"] == traefik_endpoint:
                        print(f"Record for {host} already points to {traefik_endpoint}, skipping update")
                    
                    else:
                        print(f"Updating CNAME record for {host} to {traefik_endpoint}")

                        record["content"] = traefik_endpoint
                        cf.zones.dns_records.put(zone_id, record["id"], data=record)
                else:
                    print(f"Found existing record for {host} but it is not a CNAME, skipping update")
        
        if not found_record:
            print(f"Creating new CNAME record for {host} to {traefik_endpoint}")

            new_record = {
                "name": host,
                "type": "CNAME",
                "content": traefik_endpoint,
                "proxied": False

            }

            cf.zones.dns_records.post(zone_id, data=new_record, ttl=5 * 60) # 5 minutes


def main():
    # setup the namespace
    ns = os.getenv("K8S_NAMESPACE")
    if ns is None:
        ns = ""

    # configure client 
    config.load_incluster_config()
    api = client.CoreV1Api()

    traefik_endpoint = ""

    def update_traefik_endpoint():
        nonlocal traefik_endpoint

        services = api.list_namespaced_service(namespace=ns, watch=False)
        new_endpoint = get_traefik_endpoint(services.items)

        if traefik_endpoint != new_endpoint:
            traefik_endpoint = new_endpoint

            print(f"Traefik endpoint: {traefik_endpoint}")

    update_traefik_endpoint()

    c_api = client.CustomObjectsApi()

    # setup watch
    while True:
        try:
            w = watch.Watch()
            for res in w.stream(c_api.list_cluster_custom_object, group="traefik.io", version="v1alpha1", plural="ingressroutes", timeout_seconds=0, _request_timeout=120):
                if res.get("type") == "ADDED" or res.get("type") == "MODIFIED":
                    ingress_hosts = get_ingress_hostnames(res["object"])
                    
                    if ingress_hosts:
                        update_traefik_endpoint()

                        print(f"Found new/updated ingress: {ingress_hosts}")

                        setup_cname_for_ingress(ingress_hosts, traefik_endpoint)
                
                elif res.get("type") == "DELETED":
                    update_traefik_endpoint()

                    print(f"Deleted ingress: {res['object']['metadata']['name']}")

                    ingress_hosts = get_ingress_hostnames(res["object"])

                    print("   Hosts: ", ingress_hosts)

                    # note: no cleanup, do it manually for now
        
        except urllib3.exceptions.ReadTimeoutError:
            print("ReadTimeoutError, retry")
            pass

if __name__ == '__main__':
    print("Starting ingress Watcher")
    main()
