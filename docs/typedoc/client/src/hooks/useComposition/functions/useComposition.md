[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/useComposition](../README.md) / useComposition

# Function: useComposition()

> **useComposition**\<`T`\>(`options?`): [`UseCompositionReturn`](../interfaces/UseCompositionReturn.md)\<`T`\>

Defined in: [client/src/hooks/useComposition.ts:37](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/useComposition.ts#L37)

Provides IME-safe keyboard handling for `<input>` and `<textarea>` elements.

Prevents `Enter` (without Shift) and `Escape` from firing while a CJK composition
session is in progress. A Safari workaround defers the composition-end state reset
via two nested `setTimeout` calls so that `onKeyDown` fires before the composing
flag is cleared.

## Type Parameters

### T

`T` *extends* `HTMLInputElement` \| `HTMLTextAreaElement` = `HTMLInputElement`

## Parameters

### options?

[`UseCompositionOptions`](../interfaces/UseCompositionOptions.md)\<`T`\> = `{}`

Optional upstream handlers for `onKeyDown`, `onCompositionStart`,
  and `onCompositionEnd` that are forwarded after the IME guard logic.

## Returns

[`UseCompositionReturn`](../interfaces/UseCompositionReturn.md)\<`T`\>

`{ onCompositionStart, onCompositionEnd, onKeyDown, isComposing }` — spread
  these onto the target input element. `isComposing()` can be called imperatively to
  check whether a composition session is active.
