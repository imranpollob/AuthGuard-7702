import pandas as pd
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

API_KEY = os.getenv("ETHERSCAN_API_KEY", "YOUR_ETHERSCAN_API_KEY")
BASE_URL = "https://api.etherscan.io/v2/api"

CHAIN_MAP = {
    'ethereum': 1,
    'polygon': 137,
    'optimism': 10,
    'arbitrum': 42161,
    'bnb': 56,
    'base': 8453,
    'gnosis': 100
}

INPUT_FILE = "merged.csv"
OUTPUT_FILE = "composite_ca_address.xlsx"

def get_contract_creation_transactions(address, chain_name, retries=3, delay=5):
    chain_id = CHAIN_MAP[chain_name]
    params = {
        "chainid": chain_id,
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": 100,
        "sort": "asc",
        "apikey": API_KEY
    }

    for attempt in range(retries):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'result' not in data:
                print(f"[{chain_name}] Unexpected response for {address}: {data}")
                return []

            transactions = data['result']
            contract_creations = [
                tx for tx in transactions if tx.get('to') in (None, '', '0x0000000000000000000000000000000000000000')
            ]

            return [
                {
                    "chain": chain_name,
                    "from": address,
                    "ca_address": tx.get("contractAddress", "")
                }
                for tx in contract_creations
            ]
        except Exception as e:
            print(f"[{chain_name}] Error for {address}: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Failed after {retries} attempts for {address}")
                return []

def get_all_contract_creations(df_input):
    all_results = []
    tasks = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        for _, row in df_input.iterrows():
            address = str(row['potential_suspect_creator']).lower()
            chain_name = str(row['chain']).lower()
            if chain_name not in CHAIN_MAP:
                print(f"[WARN] Unsupported chain: {chain_name}")
                continue
            tasks.append(executor.submit(get_contract_creation_transactions, address, chain_name))

        for future in as_completed(tasks):
            result = future.result()
            if result:
                all_results.extend(result)

    df_output = pd.DataFrame(all_results)
    df_output.to_excel(OUTPUT_FILE, index=False)
    print(f"[+] Saved {len(df_output)} contract creation transactions to {OUTPUT_FILE}")

if __name__ == "__main__":
    df_input = pd.read_csv(INPUT_FILE)
    get_all_contract_creations(df_input)
