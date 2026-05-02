const RAILWAY_API = "https://backboard.railway.app/graphql/v2";

export interface RailwayService {
  id: string;
  name: string;
  projectId: string;
  projectName: string;
  environmentId: string | null;
}

async function railwayQuery(
  token: string,
  query: string,
  variables?: Record<string, unknown>,
): Promise<unknown> {
  const resp = await fetch(RAILWAY_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!resp.ok) throw new Error(`Railway API error: ${resp.status}`);
  const result = (await resp.json()) as {
    data?: unknown;
    errors?: { message: string }[];
  };
  if (result.errors?.length) {
    throw new Error(`Railway GraphQL error: ${result.errors[0].message}`);
  }
  return result;
}

export async function listRailwayServices(
  token: string,
): Promise<RailwayService[]> {
  const query = `
    query {
      projects {
        edges {
          node {
            id
            name
            environments { edges { node { id name } } }
            services { edges { node { id name } } }
          }
        }
      }
    }
  `;

  const result = (await railwayQuery(token, query)) as {
    data?: {
      projects?: {
        edges?: Array<{
          node: {
            id: string;
            name: string;
            environments: { edges: Array<{ node: { id: string; name: string } }> };
            services: { edges: Array<{ node: { id: string; name: string } }> };
          };
        }>;
      };
    };
  };

  const edges = result.data?.projects?.edges;
  if (!edges) throw new Error("Unexpected Railway API response: missing projects.edges");

  const services: RailwayService[] = [];
  for (const { node: project } of edges) {
    const envId = project.environments.edges[0]?.node.id ?? null;
    for (const { node: service } of project.services.edges) {
      services.push({
        id: service.id,
        name: service.name,
        projectId: project.id,
        projectName: project.name,
        environmentId: envId,
      });
    }
  }
  return services;
}

export async function upsertRailwayVariables(
  token: string,
  projectId: string,
  serviceId: string,
  environmentId: string,
  vars: Record<string, string>,
): Promise<void> {
  const mutation = `
    mutation VariableUpsert($input: VariableUpsertInput!) {
      variableUpsert(input: $input)
    }
  `;
  for (const [name, value] of Object.entries(vars)) {
    await railwayQuery(token, mutation, {
      input: { projectId, serviceId, environmentId, name, value },
    });
  }
}

export async function deleteRailwayVariables(
  token: string,
  projectId: string,
  serviceId: string,
  environmentId: string,
  names: string[],
): Promise<void> {
  const mutation = `
    mutation VariableDelete($input: VariableDeleteInput!) {
      variableDelete(input: $input)
    }
  `;
  for (const name of names) {
    await railwayQuery(token, mutation, {
      input: { projectId, serviceId, environmentId, name },
    });
  }
}
