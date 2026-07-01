[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/ErrorBoundary](../README.md) / default

# Class: default

Defined in: [client/src/components/ErrorBoundary.tsx:21](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ErrorBoundary.tsx#L21)

React class component that catches render errors thrown anywhere in its
child subtree. Uses `getDerivedStateFromError` to transition into an
error state, then renders a fallback UI showing the error stack trace
and a "Reload Page" button that calls `window.location.reload()`.
In the normal (no-error) case it renders `children` unchanged.

## Extends

- `Component`\<`Props`, `State`\>

## Constructors

### Constructor

> **new default**(`props`): `ErrorBoundary`

Defined in: [client/src/components/ErrorBoundary.tsx:22](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ErrorBoundary.tsx#L22)

#### Parameters

##### props

`Props`

#### Returns

`ErrorBoundary`

#### Overrides

`Component<Props, State>.constructor`

## Methods

### render()

> **render**(): `string` \| `number` \| `bigint` \| `boolean` \| `Element` \| `Iterable`\<`ReactNode`, `any`, `any`\> \| `Promise`\<`AwaitedReactNode`\> \| `null` \| `undefined`

Defined in: [client/src/components/ErrorBoundary.tsx:31](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ErrorBoundary.tsx#L31)

#### Returns

`string` \| `number` \| `bigint` \| `boolean` \| `Element` \| `Iterable`\<`ReactNode`, `any`, `any`\> \| `Promise`\<`AwaitedReactNode`\> \| `null` \| `undefined`

#### Overrides

`Component.render`

***

### getDerivedStateFromError()

> `static` **getDerivedStateFromError**(`error`): `State`

Defined in: [client/src/components/ErrorBoundary.tsx:27](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ErrorBoundary.tsx#L27)

#### Parameters

##### error

`Error`

#### Returns

`State`
