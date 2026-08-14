# L17 retrieval topology

One dependency chain, seven blobs in, one callable tool out. Two paths carry the
lesson: the **scanned PNG**, which proves six stages in a single query result,
and the **.wav**, which proves a green run can index nothing at all.

## Which diagram to put on screen

The full chain is **13 ranks deep**. It renders about 0.44:1 tall or 8.35:1 wide,
so it does not fit a 16:9 frame at readable size either way. Use the two beat
diagrams on camera and keep the full chain as the reference.

| On camera | Use |
| --- | --- |
| Beat 2, ingestion | **Diagram A** below. Fits the frame. |
| Beat 3, retrieval | **Diagram B** below. Fits the frame. |
| README, GitHub, reference | **Diagram C**, the full chain. Scroll it. |

---

## Diagram A -- Beat 2: seven blobs in, eleven chunks out

```mermaid
flowchart LR
    MD["5 markdown<br>text layer"] --> DS
    PNG[/"1 scanned PNG<br>pixels, no text"/] -- "the OCR path" --> DS
    WAV[\"1 .wav audio"\] --> DS
    DS(["1 DATA SOURCE"]) --> IXR{{"2 INDEXER<br>imageAction is HERE"}}
    IXR -- "attaches,<br>never runs alone" --> SS["3 SKILLSET<br>OCR, Merge, Split, Embed"]
    SS --> PROJ["index projections<br>1 chunk = 1 document"]
    PROJ --> IDX[("4 INDEX<br>11 chunks<br>10 md, 1 png")]
    WAV -. "no codec" .-> DEAD["DEAD END, 0 chunks<br>run says SUCCESS<br>7 processed, 0 failed"]

    classDef deadend stroke-width:4px,stroke-dasharray:7 4
    classDef ocrpath stroke-width:3px
    class WAV,DEAD deadend
    class PNG ocrpath
```

**Point at:** the four numbered objects, then the dashed dead end. The `.wav` is
counted as **processed** and contributes **zero**. A warning, not a failure.

---

## Diagram B -- Beat 3: one index, four query modes, one callable tool

```mermaid
flowchart LR
    IDX[("INDEX<br>11 chunks")] --> BM25["keyword BM25<br>exact tokens"]
    IDX --> HYB["hybrid<br>rank fusion"]
    IDX --> VEC["pure vector<br>paraphrase"]
    BM25 --> SEM["semantic reranker<br>reorders,<br>never retrieves"]
    HYB --> SEM
    VEC -. "needs semanticQuery,<br>NOT queryType" .-> SEM
    SEM --> KS["knowledge source<br>WHAT content"]
    KS --> KB["knowledge base<br>HOW to retrieve"]
    KB --> AGT["Foundry agent<br>retrieve action"]
    KB --> MCP["MCP tool<br>knowledge_base_retrieve"]

    classDef noop stroke-width:4px,stroke-dasharray:7 4
    class VEC noop
```

**Point at:** the dashed vector edge. That is the **silent no-op** -- HTTP 200,
results returned, reranker never invoked. Raising `k` would not have fixed it.

---

## Diagram C -- the full chain, for reference

Read it top to bottom. The four numbered objects are Beat 1, the chain down to
the index is Beat 2, and everything below the index is Beat 3.

```mermaid
%%{init: {"flowchart": {"rankSpacing": 45, "nodeSpacing": 30, "padding": 14}}}%%
flowchart TD
    subgraph SRC["Blob storage: 7 blobs"]
        MD["5 markdown<br>text layer"]
        PNG[/"1 scanned PNG<br>pixels, no text layer"/]
        WAV[\"1 .wav audio"\]
    end

    subgraph AIS["Azure AI Search: the four object types"]
        DS(["OBJECT 1, DATA SOURCE<br>blob, identity connection"])
        IXR{{"OBJECT 2, INDEXER<br>imageAction is set HERE"}}
        SS["OBJECT 3, SKILLSET"]
        OCR["OCR, per image<br>pixels become text"]
        REST["Merge, per document<br>Split, per document<br>Embed, per chunk"]
        PROJ["index projections<br>1 chunk = 1 document"]
        IDX[("OBJECT 4, INDEX<br>11 chunks: 10 md, 1 png")]
    end

    DEAD["DEAD END, 0 chunks<br>no codec, warning only<br>run still says SUCCESS<br>7 processed, 0 failed"]

    subgraph Q["Query layer"]
        BM25["keyword BM25<br>exact tokens"]
        VEC["pure vector<br>paraphrase"]
        HYB["hybrid<br>rank fusion"]
        SEM["semantic reranker<br>reorders, never retrieves"]
    end

    subgraph GR["Grounding contract"]
        KS["knowledge source<br>WHAT content"]
        KB["knowledge base<br>HOW to retrieve"]
    end

    subgraph CONS["Consumers"]
        AGT["Foundry agent<br>retrieve action"]
        MCP["MCP tool<br>knowledge_base_retrieve"]
    end

    MD --> DS
    PNG -- "the OCR path" --> DS
    WAV --> DS
    DS --> IXR
    IXR -- "attaches, never runs alone" --> SS
    IXR -- "normalized images" --> OCR
    SS --> OCR
    OCR -- "text rejoins the body" --> REST
    REST --> PROJ
    PROJ --> IDX
    WAV -. "no codec, nothing extracted" .-> DEAD

    IDX --> BM25
    IDX --> VEC
    IDX --> HYB
    BM25 --> SEM
    HYB --> SEM
    VEC -. "needs semanticQuery,<br>not queryType" .-> SEM
    SEM --> KS
    KS --> KB
    KB --> AGT
    KB --> MCP

    classDef deadend stroke-width:4px,stroke-dasharray:7 4
    classDef ocrpath stroke-width:3px
    class WAV,DEAD deadend
    class PNG,OCR ocrpath
```

## What to point at on camera

- **The four numbered objects.** Data source, indexer, skillset, index. Every ingestion question is "which of these four is wrong?"
- **`imageAction` is on the INDEXER.** The arrow from indexer to OCR is the dependency. No normalized images, no OCR, and the run still says success.
- **Trace the PNG.** OCR, Merge, Split, Embed, projection, index. Six stages, one citable chunk out of the 11.
- **The dashed dead end.** The .wav is counted as processed and contributes zero. A warning, not a failure.
- **Reranker sits after retrieval, not instead of it.** It reorders what BM25 and hybrid already found. It cannot rescue a miss.
