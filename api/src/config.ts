import * as fcl from "@onflow/fcl";

import * as dotenv from "dotenv";

import dotenvExpand from "dotenv-expand";

const flowAccountErrorMessaage = `
No Flow account configured.
Did you export FLOW_ADDRESS and FLOW_PRIVATE_KEY?
`;

const defaultPort = 3000;

const productionEnv = "production";
const productionDotEnv = ".env";
const localDotEnv = ".env.local";

export function getConfig() {
  const env = dotenv.config({
    path:
      process.env.NODE_ENV === productionEnv ? productionDotEnv : localDotEnv,
  });

  dotenvExpand(env);

  const port = process.env.PORT || defaultPort;

  const accessApi = process.env.FLOW_ACCESS_API;

  // const minterAddress = fcl.withPrefix(process.env.MINTER_ADDRESS!);
  const minterAddress = process.env.MINTER_ADDRESS!;
  const minterPrivateKeyHex = process.env.MINTER_PRIVATE_KEY!;

  if (!process.env.MINTER_ADDRESS || !process.env.MINTER_PRIVATE_KEY) {
    throw flowAccountErrorMessaage;
  }

  const minterAccountKeyIndex = process.env.MINTER_ACCOUNT_KEY_INDEX || 0;

  // const ProjectAddress = fcl.withPrefix(
  //   process.env.PROJECT_ADDRESS!
  // );
  const ProjectAddress = process.env.REACT_APP_CONTRACT_PROJECT!;

  return {
    port,
    accessApi,
    minterAddress,
    minterPrivateKeyHex,
    minterAccountKeyIndex,
    ProjectAddress
  };
}