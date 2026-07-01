[**IIoT Building Dashboard — TypeScript API**](../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../README.md) / [client/src/const](../README.md) / getLoginUrl

# Function: getLoginUrl()

> **getLoginUrl**(): `string`

Defined in: [client/src/const.ts:13](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/const.ts#L13)

Builds the OAuth redirect URL using VITE environment variables.

Constructs a URL pointing to `{VITE_OAUTH_PORTAL_URL}/app-auth` with `appId`,
`redirectUri`, `state` (the Base64-encoded redirect URI), and `type=signIn` as
query parameters. Must be called at runtime so the `redirectUri` reflects the
current `window.location.origin`.

## Returns

`string`

The fully-formed OAuth sign-in URL as a string.
