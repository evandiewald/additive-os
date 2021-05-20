import * as t from "@onflow/types";
import * as fcl from "@onflow/fcl";
import { FlowService } from "./flow";
import * as fs from "fs";
import * as path from "path";

const AMProjectPath = '"../../contracts/NonFungibleToken.cdc"';

class ProjectService {
  constructor(
    private readonly flowService: FlowService,
    private readonly ProjectAddress: string,
  ) {}

  update = async (updateId: number, newMetadata: {String: String}) => {
    const authorization = this.flowService.authorizeMinter();
    const transaction = fs
      .readFileSync(
        path.join(
          __dirname,
          `../../../cadence/transactions/UpdateMetadata.cdc`
        ),
        "utf8"
      );
    var stringMetadata = JSON.stringify(newMetadata)
    console.log(typeof stringMetadata)
    return this.flowService.sendTx({
      transaction,
      args: [fcl.arg(updateId, t.UInt64), fcl.arg(stringMetadata, t.String)],
      authorizations: [authorization],
      payer: authorization,
      proposer: authorization,
    });
  };

  newProject = async () => {
    const authorization = this.flowService.authorizeMinter();
    const transaction = fs
      .readFileSync(
        path.join(
          __dirname,
          `../../../cadence/transactions/InitProject.cdc`
        ),
        "utf8"
      );
    return this.flowService.sendTx({
      transaction,
      args: [],
      authorizations: [authorization],
      payer: authorization,
      proposer: authorization,
    });
  };

  getCollectionIds = async (account: string): Promise<number[]> => {
    const script = fs
      .readFileSync(
        path.join(
          __dirname,
          `../../../cadence/scripts/GetIDs.cdc`
        ),
        "utf8"
      );

    return this.flowService.executeScript<number[]>({
      script,
      args: [fcl.arg(account, t.Address)],
    });
  };

  getMetadata = async (projectId: number): Promise<number[]> => {
    const script = fs
      .readFileSync(
        path.join(
          __dirname,
          `../../../cadence/scripts/CheckMetadata.cdc`
        ),
        "utf8"
      );

    return this.flowService.executeScript<number[]>({
      script,
      args: [fcl.arg(projectId, t.UInt64)],
    });
  };

}

export { ProjectService };