import requests

def call_api(url):
    try:
        response_status = requests.get(url)
        response_status.raise_for_status()
        data = response_status.json()
        return data
    except Exception as error:
        # _LOGGER.error(error)
        print(error)
        return None

def call_api_get_staking_validator(domain, operator_addr):
    url = f"{domain}/cosmos/staking/v1beta1/validators/{operator_addr}"
    return call_api(url)

def call_api_get_staking_validator_delegations(domain, operator_addr):
    url = f"{domain}/cosmos/staking/v1beta1/validators/{operator_addr}/delegations"
    return call_api(url)

domain = "http://167.172.85.52:1317"

addr = "cosmosvaloper1uk4ze0x4nvh4fk0xm4jdud58eqn4yxhrdt795p"

print(call_api_get_staking_validator(domain, addr))
print(call_api_get_staking_validator_delegations(domain, addr)["delegation_responses"][0])