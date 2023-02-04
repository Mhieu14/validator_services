import requests

from utils.logging import get_logger
from database import Database

_LOGGER = get_logger(__name__)

async def call_api(url):
    try:
        response_status = requests.get(url)
        response_status.raise_for_status()
        data = response_status.json()
        return data
    except Exception as error:
        _LOGGER.error(error)
        return None

async def call_api_get_staking_validator(domain, operator_addr):
    url = f"{domain}/cosmos/staking/v1beta1/validators/{operator_addr}"
    result = await call_api(url)
    return result

async def call_api_get_staking_validator_delegations(domain, operator_addr):
    url = f"{domain}/cosmos/staking/v1beta1/validators/{operator_addr}/delegations"
    result = await call_api(url)
    return result

async def get_validator_info_rest_api(node, chain_info, chain_stake_info):
    print(chain_stake_info)
    validator_address = node['validator'].get('validator_address')
    validator_info_await = await call_api_get_staking_validator(chain_info["rest"], validator_address)
    validator_delegations_info_await = await call_api_get_staking_validator_delegations(chain_info["rest"], validator_address)

    if (validator_info_await is None or validator_delegations_info_await is None): 
        return None
    
    decimal = chain_info["decimal"]
    validator_info = validator_info_await["validator"]
    validator_delegations_info = validator_delegations_info_await["delegation_responses"]
    voting_power = int(validator_info["tokens"])  / (10 ** decimal)
    total_tokens = chain_stake_info["tokens_bonded"]

    seft_delegation_info = None
    for delegation in validator_delegations_info:
        if (delegation["delegation"]["validator_address"] == validator_address):
            seft_delegation_info = delegation

    return {
        "operatorAddress": validator_address,
        "selfBond": int(seft_delegation_info["balance"]["amount"]) / (10 ** decimal),
        "votingPower": voting_power,
        "votingPercentage": voting_power / total_tokens * 100,
        "denom": seft_delegation_info["balance"]["denom"],
        "jailed": validator_info["jailed"],
        "commissionRate": float(validator_info["commission"]["commission_rates"]["rate"]) * 100,
        "commissionMaxRate": float(validator_info["commission"]["commission_rates"]["max_rate"]) * 100,
        "commissionMaxChangeRate": float(validator_info["commission"]["commission_rates"]["max_change_rate"]) * 100,
    }