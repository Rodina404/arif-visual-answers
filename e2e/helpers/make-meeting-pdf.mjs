// Writes fixtures/pdfs/meeting_sample.pdf: a clearly labelled, FICTIONAL meeting transcript in Egyptian
// Arabic mixed with English terms (3 decisions, 4 action items with owners and dates) for the agent demo.
// Chromium draws Arabic in visual order with shaped glyphs, like most real Arabic PDFs, so it also
// exercises the parser's visual-to-logical fix. Run: node e2e/helpers/make-meeting-pdf.mjs
import { chromium } from '@playwright/test'
import path from 'node:path'

const OUT = path.resolve(import.meta.dirname, '../../fixtures/pdfs/meeting_sample.pdf')

const LINES = [
  ['منى', 'صباح الخير يا جماعة، النهارده عايزين نقفل خطة الـ launch بتاع الـ mobile app.'],
  ['كريم', 'الـ API لسه فيه مشكلة في الـ login مع الـ SSO.'],
  ['منى', 'تمام، قررنا إن الـ launch هيكون يوم 15 ديسمبر بدل 1 ديسمبر.'],
  ['سارة', 'الـ onboarding screens محتاجة مراجعة قبل الـ launch.'],
  ['عمر', 'أنا شايف إننا نعمل beta مقفولة الأول.'],
  ['منى', 'متفقين، قررنا نعمل closed beta لـ 50 مستخدم بس.'],
  ['كريم', 'وبالنسبة للـ payments؟'],
  ['منى', 'قررنا نأجل الـ payments للـ version 2 ومش هتبقى في الـ launch.'],
  ['منى', 'يلا نوزع الـ action items.'],
  ['منى', 'كريم هيصلّح مشكلة الـ SSO login قبل 20 نوفمبر.'],
  ['منى', 'سارة هتسلّم الـ onboarding designs الجديدة يوم 25 نوفمبر.'],
  ['منى', 'عمر هيجهز test plan للـ closed beta قبل 1 ديسمبر.'],
  ['منى', 'وأنا هبعت الـ beta invites للـ 50 مستخدم يوم 5 ديسمبر.'],
  ['عمر', 'تمام، نتقابل الأسبوع الجاي نشوف الـ progress.'],
]

const html = `<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>
body { font-family: Arial, sans-serif; font-size: 14px; margin: 48px 56px; color: #111; }
.sample { direction: ltr; text-align: left; border: 2px solid #b00; color: #b00; font-weight: bold; padding: 6px 10px; margin-bottom: 18px; }
h1 { font-size: 20px; margin: 0 0 6px; }
.meta { color: #444; margin: 0 0 16px; }
p { margin: 0 0 9px; }
b { font-weight: bold; }
</style></head><body>
<div class="sample">SAMPLE - fictional meeting transcript for the Arif demo. Names, dates and numbers are invented.</div>
<h1>نص اجتماع تجريبي: فريق Nile Learning.</h1>
<p class="meta">اجتماع خيالي يوم 2 نوفمبر 2026. الحاضرين: منى (Product)، كريم (Backend)، سارة (Design)، عمر (QA).</p>
${LINES.map(([who, text]) => `<p><b>${who}:</b> ${text}</p>`).join('\n')}
</body></html>`

const browser = await chromium.launch()
const page = await browser.newPage()
await page.setContent(html)
await page.pdf({ path: OUT, format: 'A4' })
await browser.close()
console.log('wrote', OUT)
