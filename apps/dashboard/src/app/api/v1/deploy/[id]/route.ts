import { getDeployment } from "@/lib/db/queries";
import { createGetByIdHandler } from "@/lib/api/handlers";

export const GET = createGetByIdHandler(getDeployment);
