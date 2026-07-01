[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/utils](../README.md) / cn

# Function: cn()

> **cn**(...`inputs`): `string`

Defined in: [client/src/lib/utils.ts:10](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/utils.ts#L10)

Merges class names using clsx and deduplicates conflicting Tailwind classes via tailwind-merge.

## Parameters

### inputs

...`ClassValue`[]

One or more class values (strings, arrays, objects, etc.) accepted by clsx.

## Returns

`string`

A single deduplicated class string safe to pass to `className`.
