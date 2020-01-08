*** Settings ***

Resource       cumulusci/robotframework/Salesforce.robot
Resource  cumulusci/robotframework/CumulusCI.robot

Force Tags    bulkdata

*** Test Cases ***

Test Run Bulk Data Deletion With Error

    ${account_name} =  Generate Random String
    ${account_id} =  Salesforce Insert  Account
    ...  Name=${account_name}
    ...  BillingStreet=Baker St.

    ${contract_id} =    Salesforce Insert  Contract
    ...  AccountId=${account_id}

    Salesforce Update    Contract    ${contract_id}
    ...     status=Activated

    ${opportunity} =    Salesforce Insert   Opportunity
    ...  AccountId=${account_id}
    ...  StageName=Prospecting
    ...  Name=${account_name}
    ...  CloseDate=2025-05-05

    Run Keyword and Expect Error        *BulkDataException*
    ...     Run Task Class   cumulusci.tasks.bulkdata.delete.DeleteData
    ...         objects=Account
    ...         where=BillingStreet='Baker St.'

