# Migration Notes

- 0014: deployments.api_key_hash added. Existing deployments get new random keys; update SDK config with the key from GET /api/v1/deploy/{id}.
