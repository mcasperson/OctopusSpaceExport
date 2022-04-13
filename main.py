import argparse
import signal
import sys
import time
import urllib

from requests import get
from requests import post
from requests.auth import HTTPBasicAuth
from retrying import retry

parser = argparse.ArgumentParser(description='Export all projects.')
parser.add_argument('--octopusUrl',
                    dest='octopus_url',
                    action='store',
                    help='The Octopus server URL',
                    required=True)
parser.add_argument('--octopusApiKey',
                    dest='octopus_api_key',
                    action='store',
                    help='The Octopus API key',
                    required=True)
parser.add_argument('--octopusSpace',
                    dest='octopus_space',
                    action='store',
                    help='The Octopus space',
                    required=True)
parser.add_argument('--exportPassword',
                    dest='export_password',
                    action='store',
                    help='The exported archive password',
                    required=True)
parser.add_argument('--excludedProjects',
                    dest='excluded_projects',
                    action='store',
                    help='Projects to exclude from the export',
                    required=False)

args = parser.parse_args()

headers = {"X-Octopus-ApiKey": args.octopus_api_key}

cancelled = False


def handler(signum, frame):
    global cancelled
    cancelled = True
    print("loop was cancelled")


signal.signal(signal.SIGINT, handler)


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_space_id(space_name):
    url = args.octopus_url + "/api/spaces?partialName=" + urllib.parse.quote(space_name.strip()) + "&take=1000"
    response = get(url, headers=headers)
    spaces_json = response.json()

    filtered_items = [a for a in spaces_json["Items"] if a["Name"] == space_name.strip()]

    if len(filtered_items) == 0:
        sys.stderr.write("The space called " + space_name + " could not be found.\n")
        return None

    first_id = filtered_items[0]["Id"]
    return first_id


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_resource_id(space_id, resource_type, resource_name):
    if space_id is None:
        return None

    url = args.octopus_url + "/api/" + space_id + "/" + resource_type + "?partialName=" \
          + urllib.parse.quote(resource_name.strip()) + "&take=1000"
    response = get(url, headers=headers)
    json = response.json()

    filtered_items = [a for a in json["Items"] if a["Name"] == resource_name.strip()]
    if len(filtered_items) == 0:
        sys.stderr.write("The resource called " + resource_name + " could not be found in space " + space_id + ".\n")
        return None

    first_id = filtered_items[0]["Id"]
    return first_id


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_resource(space_id, resource_type, resource_id):
    if space_id is None:
        return None

    url = args.octopus_url + "/api/" + space_id + "/" + resource_type + "/" + resource_id
    response = get(url, headers=headers)
    json = response.json()

    return json


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_projects(space_id):
    if space_id is None:
        return None

    url = args.octopus_url + "/api/" + space_id + "/projects?take=1000"
    response = get(url, headers=headers)
    json = response.json()

    items = list(map(lambda p: p["Id"], json["Items"]))
    if len(items) == 0:
        sys.stderr.write("The space id " + space_id + " did not have any projects.\n")
        return None

    return items


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def create_export(space_id, projects):
    if space_id is None or len(projects) == 0:
        return None

    url = args.octopus_url + "/api/" + space_id + "/projects/import-export/export"

    excluded_projects = args.excluded_projects.split(",") if args.excluded_projects else []
    filtered_items = [a for a in projects if a not in excluded_projects]

    quoted_list = list(map(lambda p: '"' + p + '"', filtered_items))

    response = post(url, '{"IncludedProjectIds":[' + ','.join(
        quoted_list) + '],"Password":{"HasValue":true,"NewValue":"' + args.export_password + '"}}', headers=headers)

    print(response.text)

    return response.json()["TaskId"]


def download_artifacts(space_id, task_id):
    # Loop for 5 minutes or until the artifacts ar available
    for x in range(30):
        # Get the artifacts
        uri = args.octopus_url + "/api/" + space_id + "/artifacts?regarding=" + task_id
        artifacts = get(uri, headers=headers).json()

        # Download the artifacts
        for artifact in artifacts["Items"]:
            uri = args.octopus_url + "/api/" + space_id + "/artifacts/" + artifact["Id"] + "/content"
            response = get(uri, allow_redirects=True, headers=headers)
            response.raise_for_status()
            open(artifact['Filename'], 'wb').write(response.content)
            print("Saved " + artifact['Filename'])

        if len(artifacts["Items"]) != 0 or cancelled:
            break

        # try to download the artifacts again
        print("No artifacts found - sleeping for 10 seconds before trying again")
        time.sleep(10)


space_id = get_space_id(args.octopus_space)
projects = get_projects(space_id)
task_id = create_export(space_id, projects)
download_artifacts(space_id, task_id)
