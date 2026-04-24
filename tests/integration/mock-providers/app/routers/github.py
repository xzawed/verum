from __future__ import annotations
import secrets
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ._common import check_fault, log_call

router = APIRouter()

_FAKE_TOKEN = "gho_mock_token_for_integration_tests"
_REPO_FULL_NAME = "verum-test/arcana-mini"


@router.post("/login/oauth/access_token")
async def oauth_token(request: Request):
    log_call(request, "github/oauth/token", {})
    return JSONResponse({"access_token": _FAKE_TOKEN, "token_type": "bearer", "scope": "public_repo,read:user,user:email"})


@router.get("/user")
async def get_user(request: Request):
    log_call(request, "github/user", {})
    return JSONResponse({"id": 99999, "login": "verum-test", "email": "test@verum.dev", "name": "Verum Test"})


@router.get("/user/repos")
async def list_repos(request: Request):
    log_call(request, "github/user/repos", {})
    return JSONResponse([{
        "full_name": _REPO_FULL_NAME,
        "html_url": "http://git-http/verum-fixtures/sample-repo",
        "description": "Arcana Mini tarot service fixture",
        "default_branch": "main",
        "updated_at": "2026-01-01T00:00:00Z",
        "private": False, "fork": False, "archived": False,
    }])


@router.get("/repos/{owner}/{repo}")
async def get_repo(owner: str, repo: str, request: Request):
    log_call(request, f"github/repos/{owner}/{repo}", {})
    return JSONResponse({"full_name": f"{owner}/{repo}", "default_branch": "main", "private": False})


# Git Trees/Blobs/Refs/Commits for SDK PR creation
@router.get("/repos/{owner}/{repo}/git/ref/{ref:path}")
async def get_ref(owner: str, repo: str, ref: str, request: Request):
    log_call(request, f"github/git/ref/{ref}", {})
    return JSONResponse({"object": {"sha": "abc123mock", "type": "commit"}, "ref": f"refs/{ref}"})


@router.post("/repos/{owner}/{repo}/git/blobs")
async def create_blob(owner: str, repo: str, request: Request):
    log_call(request, "github/git/blobs", {})
    return JSONResponse({"sha": secrets.token_hex(20), "url": ""})


@router.post("/repos/{owner}/{repo}/git/trees")
async def create_tree(owner: str, repo: str, request: Request):
    log_call(request, "github/git/trees", {})
    return JSONResponse({"sha": secrets.token_hex(20), "url": "", "tree": []})


@router.post("/repos/{owner}/{repo}/git/commits")
async def create_commit(owner: str, repo: str, request: Request):
    log_call(request, "github/git/commits", {})
    return JSONResponse({"sha": secrets.token_hex(20), "url": ""})


@router.patch("/repos/{owner}/{repo}/git/refs/{ref:path}")
async def update_ref(owner: str, repo: str, ref: str, request: Request):
    log_call(request, f"github/git/refs/{ref}", {})
    return JSONResponse({"ref": f"refs/{ref}", "object": {"sha": secrets.token_hex(20)}})


@router.get("/repos/{owner}/{repo}/contents/{path:path}")
async def get_contents(owner: str, repo: str, path: str, request: Request):
    log_call(request, f"github/contents/{path}", {})
    # Return 404 so SDK PR creator treats all files as new
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Not Found")


@router.post("/repos/{owner}/{repo}/pulls")
async def create_pull(owner: str, repo: str, request: Request):
    body = await request.json()
    log_call(request, "github/pulls", body)
    return JSONResponse({
        "number": 42,
        "html_url": f"http://mock-providers/github/repos/{owner}/{repo}/pull/42",
        "head": {"sha": secrets.token_hex(20)},
    })
