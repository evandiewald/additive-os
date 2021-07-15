# additive-os
Additive OS is an experimental open-source platform for additive manufacturing data management and IP protection. 

:warning: *This platform is in early development, and we expect things to change drastically in the coming months. While files are encrypted and database access is secured using best practices, you should use the application at your own risk. Consider it a purely experimental system.*

## Overview
Additive OS is a Python client that hosts an API locally on your machine. The application is primarily browser-based, but the underlying methods can also be accessed programmatically (e.g. through a Raspberry Pi or cloud server). 
The core technologies are:
- [IPFS](https://ipfs.io/) for P2P content delivery of files 
- [MongoDB](https://www.mongodb.com/) as the database engine
- [Ethereum Smart Contracts](https://ethereum.org/en/developers/docs/smart-contracts/) to provide an independently-verifiable audit trace of the AM digital thread
- [Metamask](https://metamask.io) for transaction signing
- [AWS Key Management Store](https://aws.amazon.com/kms/) for managing/using encryption keys
- [AWS Cognito](https://aws.amazon.com/cognito/) for user authentication and permissions management

## Getting Started (new users)
:warning: This section assumes that an administration has already set up the Additive OS infrastructure (MongoDB & AWS authentication) for your facility. If you are an administrator looking to perform this setup, please check out [these instructions](#getting-started-admin).

1. Clone the repository with `$ git clone https://github.com/evandiewald/additive-os`
2. Navigate to the `client` directory with `$ cd additive-os/client`
3. Initialize and activate a virtual environment (I use virtualenv): 

`$ virtualenv venv`

`$ source venv/bin/activate` (Linux) or `>> venv\Scripts\activate.bat` (Windows)

4. Install dependencies with `$ pip install -r requirements.txt`
5. Run the web server via uvicorn `$ uvicorn main:app` (add the `--reload` tag for development)

## Getting Started (admin)
COMING SOON

## Additional Resources
**Whitepaper**: COMING SOON

**Overview Presentation (SFF 2021)**: https://youtu.be/q0A4kLxgCqE

**Usage Demo**: https://youtu.be/joYuvgcZNo4
