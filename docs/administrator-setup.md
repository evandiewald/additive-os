# Administrator Setup

This section is meant for administrators setting up Additive OS in a lab or facility setting. If you are looking for personal setup instructions, please check out [this page](personal-setup.md).

## Overview

As a platform in rapid development, it's ~possible~ likely that you experience some instability when installing or using Additive OS during this time. If you experience difficulties, please submit it an [issue](https://github.com/evandiewald/additive-os/issues). The administrator setup requires some basic familiarity with IT infrastructure, but a strong focus of future improvement is to lower the barrier to entry to this platform. If you have suggestions for improvements to this documentation (or anything else), please feel free to submit a [pull request](https://github.com/evandiewald/additive-os/pulls). 

Essentially, administrator setup involves filling out all the environment variables in [`config.py`](https://github.com/evandiewald/additive-os/blob/main/client/config.py). We need to tie together our remote database (MongoDB), smart contract (Ethereum/Remix/Infura), and authentication/encryption infrastructure (AWS). Broad overview:
- MongoDB
    - Create a cluster and add a user
- Ethereum  
    - ETH wallet
    - Deployed smart contracts  
    - Infura.io endpoint
- AWS Key Management
    - Cognito user pool/identity pool
    - IAM Roles
    - Lambda function for auth
    - API Gateway
- Running IPFS node

### Create a MongoDB Cluster
The heart of Additive OS is the MongoDB database. [These instructions](https://docs.atlas.mongodb.com/getting-started/) cover the basics of standing up a cluster on their Free Tier. The MongoDB Free Tier does not expire, and provides plenty of functionality for our purposes. You will notice that a common theme of Additive OS is that many infrastructure decisions were made to minimize cost, especially for testing. Here are the general steps, with links to MongoDB docs for step-by-step instructions:
1. [Create an Atlas Account](https://docs.atlas.mongodb.com/tutorial/create-atlas-account/)
2. [Deploy a Free Tier Cluster](https://docs.atlas.mongodb.com/tutorial/deploy-free-tier-cluster/)
  - I recommend you choose AWS as the cloud provider to keep consistent with our authentication infrastructure.
4. [Configure IP Access List](https://docs.atlas.mongodb.com/security/add-ip-address-to-list/)
  - Keep in mind that you will need to open up access to ANY IP if you want to allow other users to access the database on their own computers
5. [Create MongoDB User for Cluster](https://docs.atlas.mongodb.com/tutorial/create-mongodb-user-for-cluster/)
  - Depending on the situation, you may want to either allow read/write or read-only access to users
  - Take note of this username and password
6. Use Atlas to Create a database called `amblockchain` with the following collections:
  - `build-entries`
  - `build-trees`
  - `files`
  - `license-data`
  - `project-data`
7. **Get your connection string**, which is of the form `mongodb+srv://<username>:<password>@<cluster-name>.xgcio.mongodb.net/amblockchain`

#### Environment variables
`MONGO_CONNECTION_STRING = "mongodb+srv://<username>:<password>@<cluster-name>.xgcio.mongodb.net/amblockchain?ssl=true&ssl_cert_reqs=CERT_NONE"`

### Create an ETH Wallet with Metamask
We recommend using the [Metamask](https://metamask.io/) browser extension to create and manage your Ethereum wallets. Creating a new wallet generates an asymmetric public/private key pair. Metamask securely and conveniently manages your keys for you, but it's good practice to also store them in a safe place. The most important thing to remember is that you should **NEVER share your private key**, as this is used to sign transactions (such as spending ETH) on your behalf. If you want to learn more about Ethereum and wallet providers, [this link](https://ethereum.org/en/wallets/) is a good place to start.
Ethereum provides several Testnets that can be used to test out applications without spending real ETH. We recommend using a Testnet for your initial deployment, especially if you have never worked with smart contracts before. This approach is free, but less stable and secure than the Ethereum Mainnet, which should be used in any production scenarios.

#### Fund your account
The rest of these instructions will assume that you are using the **Ropsten Testnet** to deploy the smart contract for your facility, but the procedures are similar for Mainnet deployments.
To obtain some Fake ETH for the Ropsten Testnet, paste your wallet address into a faucet like [this one](https://faucet.ropsten.be/). It may take several minutes for the deposit to go through, but eventually you should see a balance of about 1 ETH in your Metamask wallet, which should be plenty for our purposes. If using the Mainnet, you can purchase ETH from a verified exchange.

### Deploy smart contracts with Remix IDE
Now that your wallet is funded, the next step is to deploy the **AMProject** and **AMLicense** smart contracts

### Generate an Infura endpoint

### AWS Configuration

### Run an IPFS node
