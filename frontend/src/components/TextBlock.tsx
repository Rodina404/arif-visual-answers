import Markdown from 'react-markdown'
import type { TextProps } from '../catalog/schemas'
import { stripUrls } from '../lib/text'
import { Card } from './Card'
import type { Verification } from '../state/useAnswer'

const ALLOWED = ['p', 'strong', 'em', 'ul', 'ol', 'li', 'code']

/** Limited markdown. No rehype-raw; raw HTML is escaped so it shows as literal text, never markup. */
export function TextBlock({ props, verification }: { props: TextProps; verification?: Verification }) {
  // "&lt;" is a markdown entity: `<img ...>` renders as the literal characters, not as an HTML node.
  const safe = stripUrls(props.body).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  return (
    <Card lang={props.lang} type="text" title={props.title} verification={verification}>
      <div dir="auto" className="text-sm leading-7 text-ink [&_li]:my-1 [&_ol]:ps-5 [&_p]:my-2 [&_ul]:list-disc [&_ul]:ps-5 [&_ol]:list-decimal">
        <Markdown allowedElements={ALLOWED} unwrapDisallowed skipHtml={false}>
          {safe}
        </Markdown>
      </div>
    </Card>
  )
}
