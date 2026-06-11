# Image Inventory

Last updated: 2026-06-11 21:29 KST

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

## 2026-06-10 Local Images After pdf2docx Static Worker

These images were rebuilt and smoke-tested locally after switching `pdf2docx-worker` to the static anchored base image. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:f676c495dd8cd25eb47762953fc9bb4439e4b140e48aa58021267fc0a13881df` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:eda7e1f86a51301337cbd0980e25736ddc7ebd57b42ed72e0bb2826555fa0010` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:fa2a940c392cef3c909e10c7e24f222d76bb6d55162d268c3c703eed4d8fa678` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:fba76a3ad2470705ec6d41b1a64aa0fbe8c221a339be7792d98995900a3a6805` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:af22f1cc22d4dc1c29b4fa7ee983dbd0cf1b9cc4402e3330fa0691522e77a995` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:4e51e034ffd21a5ee261e34dfe3965ddd538ef44e1bbdb8637059f5cce59d505` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:107a4c8830a6d4b2f359f10e15ec1cf8fd2fa5447a4c86a3992d0488543b75f9` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:45c26229b4cac113d4036e0f19a1935d32d2bd1b90ee34b6adc81f4791d7c0ae` | Not available; not pushed. |

## 2026-06-10 Local Images After pdf2docx Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding MinIO/RabbitMQ helper dependencies to `pdf2docx-worker`. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:d8e0552a706d07c1ad0dd9004fae11042951d6202a65da0b9af0bb9870551b94` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:fa75c2edaaa482573570a077f86982e6b81784704320f7b20a3a341ae813a44d` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:6f71fb8e53af0b66c872e3b4e281d01edbee088da079e66098f83e1b13726e9a` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:c1f4402610951422b14c3e45cba030e2b084fbdbe3178fbd60e545ed7025866c` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:76b1cf864c5a7c9a85fff96dd4e8db44c9b6cfdb6c777b2210761e79d5d0c420` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-10 Local Images After docx_translate Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `translate-worker` artifact/event implementation and runtime dependencies. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:74b6c35f1c3200d519e57cf10eb8528220be8b7a6b291e5247b22bd3dcb85cb1` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:4fafc1ec354dde2792044952494c1afb36da9352a62674c7e06ecc1ac3d9cd2f` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:27e017a455684681c13f3f7d387a61eb085cc5b2b924375584d12f6b2249e993` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:c1f4402610951422b14c3e45cba030e2b084fbdbe3178fbd60e545ed7025866c` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:76b1cf864c5a7c9a85fff96dd4e8db44c9b6cfdb6c777b2210761e79d5d0c420` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-10 Local Images After docx_extract Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `docx-extract-worker` artifact/event implementation and runtime dependencies. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:74b6c35f1c3200d519e57cf10eb8528220be8b7a6b291e5247b22bd3dcb85cb1` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:4fafc1ec354dde2792044952494c1afb36da9352a62674c7e06ecc1ac3d9cd2f` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:6f71fb8e53af0b66c872e3b4e281d01edbee088da079e66098f83e1b13726e9a` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:c1f4402610951422b14c3e45cba030e2b084fbdbe3178fbd60e545ed7025866c` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:76b1cf864c5a7c9a85fff96dd4e8db44c9b6cfdb6c777b2210761e79d5d0c420` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-10 Local Images After docx_replace Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `docx-replace-worker` artifact/event implementation and runtime dependencies. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:74b6c35f1c3200d519e57cf10eb8528220be8b7a6b291e5247b22bd3dcb85cb1` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:4fafc1ec354dde2792044952494c1afb36da9352a62674c7e06ecc1ac3d9cd2f` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:27e017a455684681c13f3f7d387a61eb085cc5b2b924375584d12f6b2249e993` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:fd6c713c139169f4438f40690e305270b97c65f2ca98bf9dcb0ba23b9ea5ca58` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:76b1cf864c5a7c9a85fff96dd4e8db44c9b6cfdb6c777b2210761e79d5d0c420` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-10 Local Images After docx_export Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `libreoffice-worker` `docx_export` artifact/event implementation and runtime dependencies. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:74b6c35f1c3200d519e57cf10eb8528220be8b7a6b291e5247b22bd3dcb85cb1` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:4fafc1ec354dde2792044952494c1afb36da9352a62674c7e06ecc1ac3d9cd2f` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:27e017a455684681c13f3f7d387a61eb085cc5b2b924375584d12f6b2249e993` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:fd6c713c139169f4438f40690e305270b97c65f2ca98bf9dcb0ba23b9ea5ca58` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:cdc0c81390cac1fe796921269619f7775b363e30a0bf77d4bffb4b0982fd120e` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-11 Local Images After docx_marker Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `libreoffice-worker` `docx_marker` artifact/event implementation. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:74b6c35f1c3200d519e57cf10eb8528220be8b7a6b291e5247b22bd3dcb85cb1` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:4fafc1ec354dde2792044952494c1afb36da9352a62674c7e06ecc1ac3d9cd2f` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:27e017a455684681c13f3f7d387a61eb085cc5b2b924375584d12f6b2249e993` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:fd6c713c139169f4438f40690e305270b97c65f2ca98bf9dcb0ba23b9ea5ca58` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:0582b3c3d142260b8fc409b8da80b6b171b34c6d69333db4c069ceae3d49ba7a` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:cca6db4344802c7dd3145764f2f0a64955f15176f9cc2a914aa51f95623bef57` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:53d6d15360a21fe0bc451bfb4f60c05e870aa52ae0ecbf6fbfbf01328418f38c` | Not available; not pushed. |

## 2026-06-11 Local Images After pdf2hwpx Placeholder Artifact/Event Flow

These images were rebuilt and smoke-tested locally after adding the `pdf2hwpx-worker` placeholder artifact/event implementation. The Python base image was refreshed during this build, so several local image IDs changed. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:0b6427c64791c52087d2f4595786b3f6651356fe3900de3e018468cf5f3e9804` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:bad342c177d4a6251984e4c0cf62b81a478c7b5ec0b0ae94d430dde27170ccae` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:c9220814dbdddd284bb4a94fb4f13df05f2869492bc4f334769b0bff734d56ce` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:296975f1decf29ca8a731a86e4971ab1ce7009d4e420806aaca466a8fc4c4949` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:6fd66de23018d83249401cdb2530d80c733fe52a455f4f2d9fdaa45cc349a021` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:c44f2201f24c3f9ca17e6bd7f32db1b5497e615704739146e53492777d42d57c` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:1313d27951f915cab6193c44dfd0cd709969a646071f73a7337db7cbe5be8636` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:014835c8fffcb298ec6f0890a55774a4a22c529dfad35c34d451bca883473728` | Not available; not pushed. |

## 2026-06-11 Local Images After email-worker Provider Flow

These images were rebuilt and smoke-tested locally after adding the `email-worker` mock provider artifact/event flow and runtime dependencies. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:2dd92f90a2a36cea923f7852c4c0ab9ecc666d754aa9278e6668647f981c2079` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:d330b2fee8fa4ede461490393e261a742c634a0653a652de19c8deb3339392e5` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:8d5a6859c92004becf3d16bb0c278806d401368cc830c059d77ebde8e3e190c5` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:444a12bad467bc832f2e5d35bcde127e7db278d257ddfa07392e4bfd8825a821` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:6be0c7e96c3be5e118c5e27ef55bcdfff893170f1686e85c10c07c9a18ad7f30` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:6de8a782341cba1992dc3249a279376ef50227de0a202b8675b5ad189fba1e0f` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:afa39fd46edadd7c922add735dfbd4bdac03816882ce124b099eac485ae603e0` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:163a3f82485d43f0c8f657cf55724c713464691ac6749a92ca38593eaff9d3af` | Not available; not pushed. |

## 2026-06-11 Local Images After HWPX Route Skeleton

These images were rebuilt and smoke-tested locally after adding `hwpx-worker`, HWPX translate routing, and HWPX export placeholder support. Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username in this session.

| Image | Tag | Local image id | Registry digest |
| --- | --- | --- | --- |
| `petoo/file-translation-job-service` | `0.1.0` | `sha256:8aa8c0d84076eaa2a0bec29ff8e530d7b1338f8631db575baeeb633144357c60` | Not available; not pushed. |
| `petoo/file-translation-pdf2docx-worker` | `0.1.0` | `sha256:0e25f917ea7f71e098a2ef00f8279794cedf643b68d2d97205cb0b46734bb0b1` | Not available; not pushed. |
| `petoo/file-translation-docx-extract-worker` | `0.1.0` | `sha256:8216a1c92e8ad3ef1b67a946d817172892b2117f80571767ef1d127d589a679e` | Not available; not pushed. |
| `petoo/file-translation-translate-worker` | `0.1.0` | `sha256:06aa210e2c9f33cc22e4aa504ac8aeebc116028a3d8fb1b62b7a166e904c36d5` | Not available; not pushed. |
| `petoo/file-translation-docx-replace-worker` | `0.1.0` | `sha256:36493b44a4a4ffb3958cc0b988e2561a5934db441c8ff9568c44347f5bfd7439` | Not available; not pushed. |
| `petoo/file-translation-libreoffice-worker` | `0.1.0` | `sha256:f2291eeaf9b49738efe00810725746be687a25f8fbb86218b6ae3805502dfce5` | Not available; not pushed. |
| `petoo/file-translation-pdf2hwpx-worker` | `0.1.0` | `sha256:1c871faf7dd8af40b150b8b9e7f3f9ea848a959537c578ff9bbdf9c0111ca1c2` | Not available; not pushed. |
| `petoo/file-translation-hwpx-worker` | `0.1.0` | `sha256:743405980e3e5b07cc420efc125562a12ad56a4de75e1cb142bfd9ba3d419851` | Not available; not pushed. |
| `petoo/file-translation-email-worker` | `0.1.0` | `sha256:4d70dd2137647e9acd8b5a74dcafa1a66c4c0837073744c36a542a2a63173eb0` | Not available; not pushed. |
