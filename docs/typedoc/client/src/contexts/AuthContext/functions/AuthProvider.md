[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/contexts/AuthContext](../README.md) / AuthProvider

# Function: AuthProvider()

> **AuthProvider**(`children`): `Element`

Defined in: [client/src/contexts/AuthContext.tsx:48](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/contexts/AuthContext.tsx#L48)

Provides auth context to the subtree.

Reads the persisted session from `sessionStorage` on mount and exposes `login` and
`logout` via context. Session state is written back to `sessionStorage` on login and
cleared on logout.

## Parameters

### children

React subtree that requires auth context.

#### children

`ReactNode`

## Returns

`Element`
