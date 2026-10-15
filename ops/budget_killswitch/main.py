"""Budget kill switch: when the project's budget is reached, unlink its billing account.

Triggered by Pub/Sub budget notifications (Google's "disable billing with notifications"
pattern). Once billing is off, Cloud Run stops serving and nothing more can be charged.
Re-enable from the console (Billing -> link the account to the project) if wanted.
"""
import base64
import json
import os

import functions_framework
from googleapiclient import discovery

PROJECT_ID = os.environ["TARGET_PROJECT"]
PROJECT_NAME = f"projects/{PROJECT_ID}"


@functions_framework.cloud_event
def stop_billing(cloud_event):
    data = json.loads(base64.b64decode(cloud_event.data["message"]["data"]).decode())
    cost, budget = data["costAmount"], data["budgetAmount"]
    print(f"budget notice: cost {cost} of {budget} {data.get('currencyCode', '')}")
    if cost < budget:
        return
    billing = discovery.build("cloudbilling", "v1", cache_discovery=False)
    info = billing.projects().getBillingInfo(name=PROJECT_NAME).execute()
    if not info.get("billingEnabled"):
        print("billing already disabled")
        return
    billing.projects().updateBillingInfo(name=PROJECT_NAME, body={"billingAccountName": ""}).execute()
    print(f"billing disabled for {PROJECT_ID}")
