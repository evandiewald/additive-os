import * as fcl from "@onflow/fcl";

import yargs from "yargs/yargs";
import { hideBin } from "yargs/helpers";

import initApp from "./app";
import { getConfig } from "./config";

import { FlowService } from "./services/flow";
import { ProjectService } from "./services/project"

const argv = yargs(hideBin(process.argv)).argv;

async function run() {
  const config = getConfig();

  const flowService = new FlowService(
    config.minterAddress,
    config.minterPrivateKeyHex,
    config.minterAccountKeyIndex
  );

  // Make sure we're pointing to the correct Flow Access API.
  fcl.config().put("accessNode.api", config.accessApi);

  const startAPIServer = () => {
    const projectService = new ProjectService(
      flowService,
      config.ProjectAddress
    );

    const app = initApp(projectService);

    app.listen(config.port, () => {
      console.log(`Listening on port ${config.port}!`);
    });
  };

  if (argv.dev) {
    // If we're in dev, run everything in one process.
    startAPIServer();
    return;
  } else {
    // If we're not in dev, look for flags. We do this so that
    // the worker can be started in seperate process using flag.
    // eg:
    // $> node /api/dist/index.js (starts API server)
    // $> node /api/dist/index.js --worker (starts worker)
    if (argv.worker) {
      // Start the worker only if worker is passed as as command flag.
      // See above notes for why.
    } else {
      // Default when not in dev: start the API server.
      startAPIServer();
    }
  }
}

const redOutput = "\x1b[31m%s\x1b[0m";

run().catch((e) => {
  console.error(redOutput, e);
  process.exit(1);
});