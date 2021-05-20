import express, { Request, Response, Router } from "express";
import { ProjectService } from "../services/project";
import { body } from "express-validator";
import { validateRequest } from "../middlewares/validate-request";

function initProjectRouter(ProjectService: ProjectService): Router {
  const router = express.Router();

  router.post(
    "/projects/update/:updateId",
    // [body("updateId").exists(), body("newMetadata").exists()],
    validateRequest,
    async (req: Request, res: Response) => {
        console.log("Update Id: ", req.params.updateId)
        var newMetadata: {String: String} = req.body.newMetadata
        console.log("newMetadata: ", newMetadata)
        const tx = await ProjectService.update(parseInt(req.params.updateId), newMetadata);
        return res.send({
            transaction: tx,
        });
    }
  );

  router.get(
    "/projects/collection/:account",
    async (req: Request, res: Response) => {
      const collection = await ProjectService.getCollectionIds(
        req.params.account
      );
      console.log("Account param: ", req.params.account)
      return res.send({
        collection,
      });
    }
  );

  router.get(
    "/projects/:id",
    async (req: Request, res: Response) => {
      const collection = await ProjectService.getMetadata(
        parseInt(req.params.id)
      );
      console.log("Project param: ", req.params.id)
      return res.send({
        collection,
      });
    }
  );

  router.post(
    "/projects/new",
    validateRequest,
    async (req: Request, res: Response) => {
        const tx = await ProjectService.newProject();
        return res.send({
            transaction: tx,
        });
    }
  );

  return router;
}

export default initProjectRouter;