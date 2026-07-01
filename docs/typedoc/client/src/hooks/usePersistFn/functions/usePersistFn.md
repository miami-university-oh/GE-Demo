[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/usePersistFn](../README.md) / usePersistFn

# Function: usePersistFn()

> **usePersistFn**\<`T`\>(`fn`): `T`

Defined in: [client/src/hooks/usePersistFn.ts:16](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/usePersistFn.ts#L16)

Returns a stable function reference that always delegates to the latest `fn` closure.

Unlike `useCallback`, the returned reference never changes between renders, so it is
safe to pass to child components or effect dependency arrays without causing unnecessary
re-renders. Prefer this over `useCallback` for event handlers whose identity should not
affect rendering.

## Type Parameters

### T

`T` *extends* `noop`

## Parameters

### fn

`T`

The function to stabilise. Updated on every render via a ref.

## Returns

`T`

A permanent wrapper function that forwards all calls to the current `fn`.
