# Image Inventory

Last updated: 2026-06-10 15:56 KST

## Phase 2 Local Skeleton Images

These images were built and smoke-tested locally. Docker Hub push was attempted for `petoo/file-translation-job-service:0.1.0`, but Docker returned `denied: requested access to the resource is denied`. Registry repo digests are not available until a successful push. The `local image id` values are local Docker image content IDs, not registry digests.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:fcd1ad28ee2670fcc3e10ad7bcacb826fd66d50fceb10c6d5705c80f2182e92b` | Not available; Docker Hub push denied. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:e4b25c1b7c1403abf2f91fe1d5f9fdeb7740c6e59220a9283c8dec796285209d` | Not available; Docker Hub push denied. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:3eea2c893ef7259d01272c7b4aeb623da5d14b186c705410e8917cae83ea288b` | Not available; Docker Hub push denied. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:92d50babd6469fcb3d8fd750ea1c6b367dbb064149ec6ca19018ce271338887a` | Not available; Docker Hub push denied. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:a71f671e6abb22171ebdcd7b510313da0ef70742ef5db6b3927efab2b1a6c37b` | Not available; Docker Hub push denied. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:6a171c064ce09b92e0eba0883fb789a5ad61a848f2ffa85b80910464424be581` | Not available; Docker Hub push denied. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:594b1d3b0bbf6b4e58ed6d16f76d9cfb0594da633aea64ee8d0aa586fba62e2f` | Not available; Docker Hub push denied. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:dfbf0c6300d40e72e7862e62966b5db00a67cb7d6127f47dbfee7c2f97b68906` | Not available; Docker Hub push denied. |

## 2026-06-10 Local Images After RabbitMQ Adapter Rebuild

These images were rebuilt and smoke-tested locally after adding the `job-service` RabbitMQ adapter and `pika==1.3.2`. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:eaa5f4926910377fbd7597e9ae09ddf0c5a2e8b30888ef73d0caeb18ef4bb59a` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:0f198123841aeab449931ba33154288f124e126707e812ea1f1d78794a06df06` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:38df4837755d79dc9c273f73af7d726aabb2f0b2db1f2a4b236eab75acfe7242` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:d4ea63e082ac2ecb0cc179c2c6a23cebaef6aec9985ae94a5fbb8924f97a8c96` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:8707798a95257c660fb4a05e3010c238891492339ed4f23f1b19cf5f912c6837` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:cdc83725e7da006af4c92826e2d99aa4c2ad09c7a1a1794b931318a20d1f3044` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:faaf8f6d670719fe7485c5e962eb25bf44fb1e8f31d44527ed173616ced65dec` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:943138ee2905f84c83aa2972c3e851403925e9c981be70b558af122d56414ec5` | Not available; not pushed. |

## Custom pdf2docx Base Image

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/pdf2docx` | `0.5.13-py311-static` | `sha256:53a9e395b377c5a410439148a180cba15c8ab6f70fa015159e7a177f1a70bafb` | `petoo/pdf2docx@sha256:d3ef804baceed3516e8ce89df3a33abfde00c1fd348541c3b8ad0cb9fc404f0f` |
