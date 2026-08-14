#!/usr/bin/env python
"""
AI-103 Lesson 17 - remove everything this lesson created.

    uv run python m17_teardown.py            # the search objects
    uv run python m17_teardown.py --blobs    # also empty the blob container

DELETION ORDER IS NOT OPTIONAL
------------------------------
Objects here hold references to each other, and the service enforces them:

    knowledge base   references the knowledge source
    knowledge source references the index
    indexer          references the data source, the skillset, and the index
    skillset         projects into the index

So the order is exactly the reverse of the order they were created in. To
delete a knowledge source you must first update or delete every knowledge base
that points at it -- there is no cascade.

Two things this script deliberately does NOT do:

  * It does not delete the SEARCH SERVICE. That is a control-plane operation
    and a much bigger hammer than a lesson script should be holding. The
    command is printed at the end so the decision stays a human one.
  * It does not delete the storage ACCOUNT, only the blobs it uploaded, and
    only when you ask.

Every delete tolerates a 404, so this is safe to run twice, and safe to run
after a partial build.
"""
from __future__ import annotations

import argparse

import m17_common as C
from m17_common import Fail, HttpError, Search, banner, head, kv, ok, warn


def drop(search: Search, label: str, path: str,
         api_version: str | None = None) -> None:
    try:
        search.call("DELETE", path, api_version=api_version)
        ok(f"deleted  {label:<18} {path.split('/')[-1]}")
    except HttpError as exc:
        if exc.status == 404:
            kv(f"absent   {label}", path.split("/")[-1])
            return
        warn(f"{label}: {exc.short()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blobs", action="store_true",
                        help="also delete the uploaded blobs and the container")
    args = parser.parse_args()

    settings = C.load_settings()
    search = Search(settings)
    preview = settings.preview_api_version

    banner("AI-103 L17 teardown", settings.search_endpoint)

    head("reverse dependency order")
    drop(search, "knowledge base", f"knowledgeBases/{C.KNOWLEDGE_BASE}", preview)
    drop(search, "knowledge source", f"knowledgeSources/{C.KNOWLEDGE_SOURCE}", preview)
    drop(search, "indexer", f"indexers/{C.INDEXER}")
    drop(search, "skillset", f"skillsets/{C.SKILLSET}")
    drop(search, "data source", f"datasources/{C.DATASOURCE}")
    drop(search, "index", f"indexes/{C.INDEX}")

    if args.blobs:
        head("blob storage")
        from azure.identity import AzureCliCredential
        from azure.storage.blob import BlobServiceClient
        service = BlobServiceClient(settings.blob_endpoint,
                                    credential=AzureCliCredential())
        container = service.get_container_client(C.CONTAINER)
        try:
            container.delete_container()
            ok(f"deleted  container         {C.CONTAINER}")
        except Exception as exc:
            if "ContainerNotFound" in str(exc):
                kv("absent   container", C.CONTAINER)
            else:
                warn(f"container: {exc}")

    head("still billing, and not touched by this script")
    print("  The search service itself is the expensive object in this lesson.")
    print("  Deleting the pipeline does not stop the meter. When the lesson is")
    print("  recorded and you are done retaking, run:")
    print()
    print(f"    az search service delete -n <search-service> "
          f"-g {settings.resource_group} --yes")
    print()
    print("  The system-assigned identity and its role assignments go with it.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Fail as exc:
        print(f"\n  [FAIL] {exc}")
        raise SystemExit(2)
