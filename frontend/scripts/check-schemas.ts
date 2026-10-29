/**
 * Fails if the hand-written Zod catalog drifts from the Pydantic catalog.
 * Compares a normalised "shape" (properties, required, lengths, counts, ranges, enums, patterns)
 * of z.toJSONSchema(...) against backend-exported src/catalog/schema.json.
 * Run: npm run test:schemas
 */
import { z } from 'zod'
import { COMPONENT_SCHEMAS, Citation } from '../src/catalog/schemas.ts'
import contract from '../src/catalog/schema.json' with { type: 'json' }

type J = Record<string, unknown>
const SAFE = Number.MAX_SAFE_INTEGER

function deref(node: J, defs: Record<string, J>): J {
  if (typeof node.$ref === 'string') return deref(defs[node.$ref.split('/').pop()!], defs)
  return node
}

function shape(nodeIn: J, defs: Record<string, J>): unknown {
  let node = deref(nodeIn, defs)
  const any = (node.anyOf ?? node.oneOf) as J[] | undefined
  if (any) {
    const nonNull = any.filter((b) => b.type !== 'null')
    if (nonNull.length === 1) node = deref(nonNull[0], defs)
  }
  if ('const' in node) return { const: node.const }
  if (Array.isArray(node.enum)) return { enum: [...(node.enum as unknown[])].sort() }
  const out: J = { type: node.type }
  for (const k of ['minLength', 'maxLength', 'minItems', 'maxItems', 'minimum', 'maximum', 'pattern']) {
    const v = node[k]
    if (v === undefined) continue
    if ((k === 'minimum' && v === -SAFE) || (k === 'maximum' && v === SAFE)) continue
    if (k === 'minLength' && v === 0) continue
    out[k] = v
  }
  if (node.type === 'array' && node.items) out.items = shape(node.items as J, defs)
  if (node.type === 'object' && node.properties) {
    const props = node.properties as Record<string, J>
    out.properties = Object.fromEntries(Object.keys(props).sort().map((k) => [k, shape(props[k], defs)]))
    out.required = [...((node.required as string[]) ?? [])].sort()
  }
  return out
}

function zodShape(schema: z.ZodType): unknown {
  const js = z.toJSONSchema(schema, { io: 'input', unrepresentable: 'any' }) as J
  return shape(js, (js.$defs ?? {}) as Record<string, J>)
}

const failures: string[] = []
const pairs: [string, z.ZodType, J][] = [
  ['citation', Citation, contract.citation as J],
  ...Object.entries(COMPONENT_SCHEMAS).map(
    ([k, zs]) => [k, zs as z.ZodType, (contract.components as Record<string, J>)[k]] as [string, z.ZodType, J],
  ),
]
for (const [name, zs, py] of pairs) {
  const a = JSON.stringify(zodShape(zs))
  const b = JSON.stringify(shape(py, (py.$defs ?? {}) as Record<string, J>))
  if (a !== b) failures.push(`${name}\n  zod:      ${a}\n  pydantic: ${b}`)
}
const missing = Object.keys(contract.components).filter((k) => !(k in COMPONENT_SCHEMAS))
if (missing.length) failures.push(`missing in Zod: ${missing.join(', ')}`)

if (failures.length) {
  console.error('Zod and Pydantic catalogs differ:\n' + failures.join('\n'))
  process.exit(1)
}
console.log(`schemas OK: ${pairs.length} shapes match`)
