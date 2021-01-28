import pandas as pd
from dotenv import load_dotenv
import json
from tqdm import trange
from datetime import datetime
from web3 import Web3
from dotmap import DotMap
import time
import requests
import os


class Uniswap:
    load_dotenv()
    WEB3_PROVIDER = os.getenv( "WEB3_HTTP_URI" )

    def __init__(self):
        self.w3 = Web3( Web3.HTTPProvider( self.WEB3_PROVIDER ) )
        self.factory = Web3.toChecksumAddress( "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f" )

    def get_pair_prices(self, pair, block=None, step=None):

        pair = Web3.toChecksumAddress( pair )

        with open( "UniPair.json", "r" ) as f:
            abi = f.read()
        pair_contract = self.w3.eth.contract( abi=abi, address=pair )

        with open( "ERC20.json", "r" ) as f:
            abi = f.read()

        token0_contract = self.w3.eth.contract( abi=abi, address=pair_contract.functions.token0().call() )
        token1_contract = self.w3.eth.contract( abi=abi, address=pair_contract.functions.token1().call() )

        token0_decimals = int( token0_contract.functions.decimals().call() )
        token1_decimals = int( token1_contract.functions.decimals().call() )

        if not block:
            reserves = pair_contract.functions.getReserves().call()
            reserve0 = int( reserves[0] ) / 10 ** token0_decimals
            reserve1 = int( reserves[1] ) / 10 ** token1_decimals
            return reserve1 / reserve0
        else:
            prices_list = []
            max_block = self.w3.eth.blockNumber
            min_block = max_block - block
            for i in trange( min_block, max_block, step ):
                if i > max_block:
                    break

                b = min( i, max_block )
                reserves = pair_contract.functions.getReserves().call( block_identifier=b )
                reserve0 = int( reserves[0] ) / 10 ** token0_decimals
                reserve1 = int( reserves[1] ) / 10 ** token1_decimals
                date = datetime.utcfromtimestamp( float( reserves[2] ) )
                price = reserve1 / reserve0
                prices_list.append( {"date": date, "price": price} )

            df = pd.DataFrame( prices_list )
            return df

    def get_pair(self, token0, token1):
        with open( "UniFactory.json", "r" ) as f:
            abi = json.load( f )

        factory_contract = self.w3.eth.contract( abi=abi, address=self.factory )
        token0 = Web3.toChecksumAddress( token0 )
        token1 = Web3.toChecksumAddress( token1 )
        pair = factory_contract.functions.getPair( token0, token1 ).call()
        return Web3.toChecksumAddress( pair )

    @staticmethod
    def token_info(data, decimals=False):
        """
        :param decimals:
        :param data: either symbol (dont'care for upper/lowercase, or address (checks for starting with 0x and decides)
        :return: list of [symbol or address, decimals]
        """
        url = "https://tokens.coingecko.com/uniswap/all.json"
        r = None

        while True:
            try:
                r = requests.get( url ).json()
            except requests.exceptions.Timeout:
                time.sleep( 5 )
                continue
            except requests.exceptions.TooManyRedirects as e:
                print( f"URL cannot be reached. {e}" )
                break
            except requests.exceptions.RequestException as e:
                raise SystemExit( e )
            else:
                break

        r = pd.DataFrame( r["tokens"] )

        if data.startswith( "0x" ):
            ret = r.loc[r["address"] == data, ["symbol", "decimals"]]
            ret.reset_index( drop=True, inplace=True )
            return ret.loc[0].symbol if decimals is False else ret.loc[0].decimals

        else:
            data = str( data ).upper()
            ret = r.loc[r["symbol"] == data, ["address", "decimals"]]
            ret.reset_index( drop=True, inplace=True )
            return ret.loc[0].address if decimals is False else ret.loc[0].decimals


class Etherscan:
    load_dotenv()
    ETHERS_TOKEN = os.getenv( 'ETHERSCAN_TOKEN' )

    def __init__(self):
        self.key = self.ETHERS_TOKEN
        self.url = 'https://api.etherscan.io/api?'

    def _query(self, module, params: DotMap):

        query = f'module={module}'
        for key, value in params.items():
            query += f'&{key}={value}'

        url = f'{self.url}{query}&apikey={self.key}'

        try:
            r = requests.get( url, timeout=3 )
            r.raise_for_status()
            r = r.json()
        except requests.exceptions.RequestException as err:
            return err
        except requests.exceptions.HTTPError as err:
            return err
        except requests.exceptions.ConnectionError as err:
            return err
        except requests.exceptions.Timeout as err:
            return err
        except requests.HTTPError as err:
            return err
        else:
            if r['status'] == '1':
                return r['result']

    def get_birth_block(self, address):
        module = 'account'
        params = DotMap()
        params.action = 'txlist'
        params.address = address
        params.startblock = '0'
        params.endblock = '99999999'
        params.order = 'asc'
        response = self._query( module, params )
        if response is not None:
            return int( response[0]['blockNumber'] )
        else:
            return None

    def get_tokentxns(self, address):
        module = 'account'
        params = DotMap()
        first_block = self.get_birth_block( address )

        if first_block is None:
            first_block = 0

        params.action = 'tokentx'
        params.sort = 'desc'
        params.startblock = str( first_block )
        params.endblock = 'latest'
        params.address = str( address ).lower()
        return self._query( module, params )

    def get_events(self, contract, event):
        module = 'logs'
        params = DotMap()
        first_block = self.get_birth_block( contract )
        params.action = 'getLogs'
        params.fromBlock = str( first_block )
        params.toBlock = 'latest'
        params.address = contract
        params.topic0 = event
        return self._query( module, params )

    def get_block_countdown(self, block):
        module = 'block'
        params = DotMap()
        params.action = 'getblockcountdown'
        params.blockno = block
        response = self._query( module, params )
        return response['EstimateTimeInSec']
