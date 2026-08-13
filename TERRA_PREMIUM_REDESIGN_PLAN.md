# NEXORA — 10/10 Premium Redesign Blueprint for Terra

> Design Read: Reading this as a cinematic, tactile and exact technology atelier: expressive in discovery, calm and decisive in commerce, never neon-cyberpunk and never a generic AI SaaS template.

## 0. მთავარი მიზანი

NEXORA აღარ უნდა ჰგავდეს „dark tech template“-ს. ახალი ვერსია უნდა აღიქმებოდეს როგორც საკუთარი ხასიათის მქონე პრემიუმ ტექნიკის მაღაზია, სადაც პროდუქტი, მოძრაობა, ხმა და ინტერაქცია ერთ სცენარად მუშაობს.

ახალი დიზაინის სამი სიტყვაა:

- **Tactile** — ზედაპირები, პროდუქტის ფოტოები და მოძრაობა ხელშესახებად უნდა იგრძნობოდეს.
- **Exact** — ფასები, ვარიანტები, მარაგი, შედარება და checkout უნდა იყოს მკაფიო და სწრაფი.
- **Cinematic** — მთავარი გვერდი და პროდუქტის მედია ქმნის დასამახსოვრებელ, რეჟისირებულ გამოცდილებას.

დიზაინის პარამეტრები:

- `DESIGN_VARIANCE = 9/10`
- `MOTION_INTENSITY = 8/10`
- `VISUAL_DENSITY = 5/10`

ფიზიკური მეტაფორა: **ინდუსტრიული დიზაინის სტუდია გვიან საღამოს** — მუქი გრაფიტის მაგიდა, თბილი კერამიკული ზედაპირები, ტიტანის დეტალები და ერთი მკაფიო წითელ-ნარინჯისფერი signal light.

## 1. უცვლელი საზღვრები

Terra-მ redesign-ისას აუცილებლად უნდა შეინარჩუნოს:

- Django templates, URL-ები, views, forms, CSRF და backend business logic;
- ქართული, ინგლისური და რუსული ენები;
- dark/light theme და preference persistence;
- არსებული WebGL particle engine როგორც მთავარი hero-ს ბირთვი;
- 7-ტრეკიანი ambient player;
- მუსიკაზე და მიკროფონზე WebGL რეაქცია;
- პროდუქტის გალერეა, variants, rating, reviews, wishlist, compare, cart drawer, checkout, account და AI guide;
- ლოკალური მედია და CSP/security მოთხოვნები.

არ უნდა დაემატოს React ან Framer Motion მხოლოდ ანიმაციისთვის. ეს არის Django/vanilla JavaScript პროექტი. გამოიყენოს არსებული GSAP, Web Animations API, IntersectionObserver და View Transitions API progressive enhancement-ით.

## 2. რატომ გამოიყურება მიმდინარე ვერსია 2/10-ად

კოდის აუდიტით დადასტურებული პრობლემები:

1. `Inter` + თითქმის ყველგან mono/uppercase eyebrow ტექსტი ქმნის ტიპურ AI-generated tech landing page-ს.
2. ლურჯი accent, cyan/magenta WebGL (`#00ffff` და `#ff00ff`), radial gradient და შავი canvas აჩენს generic cyberpunk/gaming იერს.
3. თითქმის ყველა ღილაკი pill-ია, თითქმის ყველა ზედაპირი მომრგვალებული card-ია, header/assistant/player glass-ია. იერარქია იკარგება, რადგან ყველაფერი ერთნაირად „დიზაინერია“.
4. ოთხი ერთნაირი product card, ერთნაირი reveal და centered CTA ქმნის შაბლონურ scroll რიტმს.
5. WebGL, hero პროდუქტის ფოტო და copy ერთმანეთზე დადებული ცალკეული ფენებია; არ ჩანს, რომ ერთი კომპოზიციის ნაწილია.
6. WebGL-ის მოძრაობა მუდმივად მუშაობს, DPR 2-მდე ადის და tab/offscreen pause არ აქვს.
7. `elastic.out` easing პრემიუმ, ზუსტ მოძრაობას არღვევს.
8. player-ის 7 პატარა ციფრიანი ღილაკი მუსიკალურ გამოცდილებად არ აღიქმება; track title, progress, volume და ვიზუალური waveform აკლია.
9. player-ის `z-index: 9499` და guide-ის `z-index: 9500` ქმნის კონკურენციას ერთსა და იმავე ქვედა კუთხეში.
10. გლობალურ `pointerdown`-ზე microphone-ის მოთხოვნის მცდელობა მოულოდნელი UX-ია. მიკროფონი უნდა ჩაირთოს მხოლოდ მის ღილაკზე შეგნებული დაჭერით.
11. `store.css` დაახლოებით 43 KB-ია და პრაქტიკულად მინიფიცირებულ გრძელ ხაზებადაა შენახული, რაც redesign-ის შემდგომ მოვლას ართულებს.

## 3. ახალი ვიზუალური მიმართულება — NEXORA / PRECISION IN MOTION

ეს არ არის:

- AI SaaS dashboard;
- RGB gaming store;
- Apple-ის ასლი;
- glassmorphism showcase;
- ერთნაირი სამი card-ის landing page;
- ყოველ სექციაში მოძრავი დეკორაციების ქაოსი.

ეს არის:

- media-first technology store;
- მკაცრი, ასიმეტრიული grid;
- მშვიდი commerce UI და ძლიერი cinematic discovery;
- რეალური პროდუქტის ფოტოები, დიდი crop-ები და ზუსტი ტიპოგრაფია;
- ერთი signature WebGL სამყარო, რამდენიმე secondary 3D moment და მიზანმიმართული micro-interactions.

პრინციპი: **ყველაფერი უნდა გრძნობდეს ცოცხლად, მაგრამ ყველაფერი მუდმივად არ უნდა მოძრაობდეს.** თუ ყოველი ელემენტი ერთდროულად მოძრაობს, პრემიუმ ეფექტი იაფი და დამღლელი ხდება.

## 4. ფერების ახალი სისტემა

მიმდინარე blue/cyan/purple პალიტრა მთლიანად იცვლება. ახალი პალიტრაა graphite + ceramic + titanium + signal vermilion.

### Dark theme

- `--bg: oklch(13% 0.012 255)` — graphite canvas;
- `--surface-1: oklch(18% 0.014 255)`;
- `--surface-2: oklch(23% 0.016 255)`;
- `--surface-3: oklch(29% 0.018 255)`;
- `--text: oklch(94% 0.010 85)` — warm titanium white, არა pure white;
- `--text-soft: oklch(72% 0.018 250)`;
- `--border: oklch(35% 0.018 255)`;
- `--signal: oklch(69% 0.20 35)` — vermilion/orange;
- `--signal-text: oklch(13% 0.018 255)`.

### Light theme

- `--bg: oklch(96.5% 0.012 88)` — warm ceramic;
- `--surface-1: oklch(99% 0.006 88)`;
- `--surface-2: oklch(92% 0.012 88)`;
- `--surface-3: oklch(87% 0.014 88)`;
- `--text: oklch(20% 0.016 255)`;
- `--text-soft: oklch(46% 0.018 255)`;
- `--border: oklch(78% 0.015 255)`;
- `--signal: oklch(65% 0.21 35)`;
- `--signal-text: oklch(14% 0.018 255)`.

### გამოყენების წესები

- signal ფერი არის ერთადერთი interactive accent: CTA, focus, selected state, cart feedback.
- titanium/champagne ტონები გამოიყენება მხოლოდ მედია/3D განათებაში და არა მეორე interactive accent-ად.
- success, warning და danger რჩება სემანტიკური და signal ფერს არ ენაცვლება.
- background-ზე აღარ იყოს generic radial-gradient blob.
- gradient დაშვებულია მხოლოდ image mask-ში, vignette-ში და shader-ში, არა ტექსტში ან card decoration-ში.
- არც CSS-ში და არც WebGL clear color-ში არ გამოიყენოს pure `#000`/`#fff`.
- ყველა text/background წყვილი შემოწმდეს WCAG AA კონტრასტზე.

### WebGL color grade

Three.js shader-ის sRGB mirror ფერები:

- deep stage: `#070A0E`;
- titanium particles: `#CBD3D8`;
- signal particles: `#FF5B38`;
- audio peak: `#FFB05A`.

`#00ffff` და `#ff00ff` სრულად ამოიღოს. აუდიო peak-ზე ფერი უნდა გათბეს titanium-დან signal/amber-მდე და არ უნდა აციმციმდეს rainbow რეჟიმში.

## 5. ტიპოგრაფია და ბრენდი

### Font system

- ძირითადი family: self-hosted **FiraGO**, რადგან ერთი სისტემით ფარავს ქართულ, ლათინურ და კირილიცას.
- body/UI: 400–550;
- product titles: 600–700;
- large display: 650–800, ხელით მორგებული tracking და line-height;
- SKU, ფასი და ციფრები: იგივე family + `font-variant-numeric: tabular-nums`; mono მხოლოდ რეალურ ტექნიკურ მონაცემზე.
- `Inter` სრულად ამოიღოს storefront-იდან.

### Wordmark

- NEXORA-სთვის გაკეთდეს custom SVG wordmark: ფართო ასოები, ერთი უნიკალური diagonal cut `X`/`R`-ში და პატარა signal dot.
- `.tech` აღარ იყოს პატარა ლურჯი suffix. თუ რჩება, იყოს მშვიდი descriptor და არა ლოგოს ნახევარი.
- wordmark SVG-ს ჰქონდეს light/dark fill token და accessible label.

### Hierarchy

- display: `clamp(3.6rem, 8vw, 9rem)`;
- page h1: `clamp(2.8rem, 5vw, 6rem)`;
- section h2: `clamp(2rem, 3.6vw, 4.5rem)`;
- body max line length: 68–72 characters;
- Georgian ტექსტს მიეცეს დაახლოებით 8–12% მეტი line-height/width budget;
- აღარ განმეორდეს uppercase eyebrow ყველა სექციაში. გამოიყენოს მხოლოდ საჭირო section index, მაგალითად `03 / AUDIO`.

## 6. Grid, spacing და surface grammar

- desktop: 12-column grid; tablet: 8; mobile: 4;
- content max-width: 1540 px;
- page gutter: `clamp(16px, 3vw, 48px)`;
- vertical rhythm: 24 / 48 / 96 / 160 px;
- controls radius: 6–8 px;
- media radius: 12–16 px;
- drawers/dialogs radius: 16–20 px;
- pills მხოლოდ tags, counters, compact toggles და segmented controls-ზე;
- product card აღარ იყოს border + rounded background card. სურათი იყოს დამოუკიდებელი media plane, ინფორმაცია კი მის ქვემოთ;
- nested cards აკრძალულია;
- glass blur გამოიყენოს მხოლოდ მაშინ, როცა ფენა რეალურად დგას მოძრავ WebGL/video-ზე. ჩვეულებრივ გვერდებზე იყოს opaque surface.

## 7. მთავარი გვერდის ახალი სცენარი

### Scene 01 — Signature WebGL hero

- სიმაღლე: 92–100svh, header-ის ქვეშ;
- layout: ასიმეტრიული, copy ქვედა-მარცხნივ, რეალური featured laptop/product მარჯვენა/ცენტრალურ სივრცეში;
- WebGL particles ქმნის სამ მდგომარეობას: dispersed field → NEXORA signal form → პროდუქტის გარშემო controlled orbit;
- pointer მოძრაობა ქმნის მხოლოდ 2–4° depth/parallax-ს;
- scroll-ის პირველ 120–140vh-ში particles ნელა იკუმშება signal line-ად და შემდეგ hero მშვიდად ტოვებს viewport-ს;
- scroll-jacking აკრძალულია: wheel/touch ბუნებრივად უნდა მუშაობდეს;
- hero copy: ერთი ძლიერი headline, ერთი წინადადება, ერთი მთავარი CTA და ერთი text link;
- არ იყოს grid overlay, generic glow blob ან ზედმეტი metric row;
- product image გამოიყენოს მხოლოდ მაშინ, თუ მოდელთან ზუსტად შესაბამისი clean მაღალი ხარისხის asset არსებობს.

### Scene 02 — Live product drop

- uniform 4-card grid-ის ნაცვლად: ერთი დიდი featured product + სამი compact product;
- დიდი პროდუქტის hover-ზე image crop ოდნავ მოძრაობს, specs კი side rail-იდან ჩნდება;
- CTA და ფასი ყოველთვის მკაფიოა; ეფექტი არ ფარავს commerce ინფორმაციას.

### Scene 03 — Category atlas

- card grid-ის ნაცვლად typographic category index;
- მარცხნივ დიდი ნომერი/სახელი, მარჯვნივ live image/video aperture;
- hover/focus-ზე preview იცვლება crossfade + 3D rotate 2°-ით;
- keyboard focus ზუსტად იმავე preview-ს მართავს;
- mobile-ზე გადაიქცეს horizontal snap rail-ად, მაგრამ არ დამალოს კატეგორიის სახელები.

### Scene 04 — Technology film

- user-ის მომავალი ვიდეო დარჩეს local `static/videos/` asset-ად;
- full-bleed 16:9 ან 21:9 frame, ძლიერი poster image, pause/play control;
- ტექსტი არ იყოს generic overlay card. copy იჯდეს ვიდეოს negative space-ში;
- `prefers-reduced-motion`-ზე autoplay გამოირთოს და გამოჩნდეს poster.

### Scene 05 — Build a setup

- ინტერაქტიული composition: laptop + monitor + audio/accessories;
- პროდუქტის არჩევაზე composited product images მსუბუქად გადაიწყოს depth layers-ში;
- ქვემოთ live total და „Add setup to bag“;
- თუ backend bundle logic ჯერ არ არსებობს, პირველი ვერსია იყოს discovery/compare-only და არ გააყალბოს cart ფუნქცია.

### Scene 06 — Curated product rail

- keyboard/touch drag horizontal rail;
- თითო slide-ში დიდი ფოტო, მოკლე reason-to-buy და ფასი;
- carousel არ უნდა autoplay-დეს.

### Scene 07 — Trust without cards

- delivery, warranty, verified media, secure checkout და support ერთ სწორხაზოვან system strip-ში;
- icons პატარა და custom stroke style-ით; არ იყოს „icon in rounded square above heading“.

### Scene 08 — Closing signal

- centered generic CTA-ის ნაცვლად oversized typographic composition + მოძრავი signal line;
- footer-ში მკაფიო columns: shop, help, account, legal, language/theme;
- social/provenance/legal მონაცემები რეალური იყოს, placeholder არა.

## 8. WOW effect storyboard

| Trigger | Effect | ტექნიკა | Fallback |
|---|---|---|---|
| პირველი ვიზიტი | particles 700–900 ms-ში აწყობს N signal-ს | existing WebGL + GSAP `expo.out` | static first frame |
| pointer hero-ზე | controlled magnetic field და 3D camera drift | shader uniform + lerp | no pointer effect |
| hero scroll exit | particle field იკუმშება ერთ signal line-ად | transform/uniform scrub | opacity transition |
| category hover/focus | media aperture იცვლის პროდუქტს depth crossfade-ით | GSAP/WAAPI | immediate swap |
| featured product hover | 2–3 layer parallax + spec reveal | CSS transform | static image |
| product card → PDP | shared product image morph | View Transitions API | normal navigation |
| Add to bag | პატარა product image მიფრინავს bag icon-მდე | cloned image + transform | toast/live region |
| theme toggle | radial iris transition toggle-იდან | View Transition pseudo-elements | instant theme switch |
| PDP gallery | zoom lens, drag/swipe, fullscreen viewer | pointer math + dialog | existing gallery |
| player active | რეალური waveform/equalizer track-ის ენერგიით | Web Audio analyser | static bars |
| mic active | WebGL density და heat იცვლება RMS/frequency-ზე | existing analyser | clear unavailable state |

არ გამოიყენოს bounce/elastic easing. ძირითადი easing: `expo.out`, `power4.out`, `power3.inOut`. ანიმირდეს `transform`, `opacity`, shader uniforms და clip-path; layout properties არა.

## 9. Player + microphone + AI guide

### Unified experience dock

- bottom-right-ში შეიქმნას ერთი `experience-dock`, რომელიც მართავს player-ს, mic-ს და ASK NEXORA-ს collision-ს;
- ვიზუალური რიგი ზემოდან ქვემოთ: microphone → player → ASK NEXORA;
- guide/cart drawer გახსნისას dock ავტომატურად გადავიდეს compact state-ში და არაფერს დაეფაროს;
- dock ყოველთვის იყოს პროდუქტის/ვიდეოს ზემოთ, მაგრამ modal/cart drawer-ის ქვემოთ;
- mobile-ზე დარჩეს safe-area-ის ზემოთ და არ დაფაროს sticky add-to-bag CTA.

### Player redesign

- collapsed: play/pause, მოკლე waveform, track number/title;
- expanded: 7 track list, current progress, seek, volume, previous/next და close;
- tiny `01–07` box grid აღარ იყოს მთავარი interface;
- player surface იყოს opaque graphite/titanium, blur მხოლოდ hero-ს თავზე;
- state შეინახოს session/localStorage-ში: selected track, volume და muted state;
- autoplay with sound-ზე არ დაეყრდნოს. პირველი რეალური user interaction-ის შემდეგ შეიძლება განახლდეს playback, browser policy-ის ფარგლებში.

### Microphone

- permission მოითხოვოს მხოლოდ microphone ღილაკზე დაჭერისას;
- ჰქონდეს clear states: off, requesting, live, denied, unavailable;
- live state იყოს subtle pulsing ring, არა blinking neon;
- ხელახლა დაჭერაზე stream track-ები რეალურად გაჩერდეს;
- მუსიკისა და mic-ის ერთდროული input არ აირიოს: მხოლოდ ერთი active analyser source.

### ASK NEXORA

- generic chat bubble-ის ნაცვლად compact „device advisor“ dock;
- panel desktop-ზე 420–480 px, mobile-ზე bottom sheet;
- answer text-ის გარდა აჩვენოს model-matched product preview, ფასი და compare/add actions;
- messages-ს ჰქონდეს მხოლოდ vertical scroll; horizontal scrollbar არასდროს;
- პასუხის ენა მიჰყვეს მომხმარებლის ბოლო შეტყობინების ენას.

## 10. Shop/catalog redesign

- shop hero გახდეს compact: title + count + search, არა მეორე landing-page hero;
- desktop-ზე sticky filter rail 260–300 px; mobile-ზე accessible filter bottom sheet;
- active filters გამოჩნდეს removable chips-ად შედეგების ზემოთ;
- sort იყოს ერთი მკაფიო select/segmented control, არა ბევრი თანაბარი text link;
- grid: 4 columns large desktop, 3 desktop, 2 tablet, 2/1 mobile პროდუქტის ტიპის მიხედვით;
- პირველი გვერდის ერთი curated item შეიძლება span 2 columns, მაგრამ pagination-ის ყველა გვერდზე არა;
- product card: borderless media plane, real image, product name, one-line value cue, price, rating და stock;
- add button desktop hover/focus-ზე ჩნდება, touch-ზე ყოველთვის ხელმისაწვდომია;
- tilt არ გაეკეთოს ყველა card-ს; მხოლოდ featured media-ს ჰქონდეს depth;
- loading, no-results, broken-media და out-of-stock states სრულად დაიდიზაინოს.

## 11. Product detail page redesign

- desktop grid: gallery 7 columns, sticky buying panel 5 columns;
- gallery: vertical thumbnails, overlay arrows, counter, swipe, keyboard arrows, high-res zoom და fullscreen dialog;
- 360° spin დაიშვას მხოლოდ მაშინ, როცა კონკრეტულ პროდუქტს რეალური თანმიმდევრული turntable frames აქვს. ჩვეულებრივი სხვადასხვა რაკურსის ფოტოები fake-360-ად არ გამოიყენოს;
- მთავარი სურათი card-ში არ ჩაიკეტოს; იყოს დიდი მშვიდი product stage;
- purchase panel-ის hierarchy: brand/category → name → rating → price → short value statement → variant → stock/delivery → quantity → CTA;
- variant buttons მკაფიო selected/hover/focus/disabled state-ებით; არჩევა რეალურად ცვლის price/stock/hidden input-ს;
- mobile-ზე sticky bottom purchase bar: price + Add to bag;
- specs იყოს მკაფიო ორ-სვეტიანი data table, არა nested cards;
- reviews: clickable 5-star control, average distribution bars, verified badge და useful review layout;
- related products section-ში არ განმეორდეს იგივე card treatment ზედიზედ; გამოიყენოს calmer horizontal rail.

## 12. Cart, checkout, auth, account და compare

### Cart drawer / bag

- 440–480 px opaque drawer;
- item image, variant, quantity stepper, price და remove action ერთ მკაფიო row-ში;
- add animation-ის ბოლოს focus/announcement სწორად იმუშაოს;
- totals და checkout CTA drawer bottom-ში sticky;
- empty state-ს ჰქონდეს ერთი curated recommendation, არა დეკორაციული ცარიელი card.

### Checkout

- distraction-free header, WebGL/video/player გარეშე;
- progress: Contact → Delivery → Review;
- form fields დაჯგუფდეს ლოგიკურად, label ყოველთვის ხილული იყოს;
- order summary desktop-ზე sticky, mobile-ზე collapsible;
- validation inline + top error summary;
- trust copy იყოს მოკლე და რეალური.

### Login/signup/password reset/verification

- split layout: form + static cinematic technology still;
- password eye button დარჩეს და იყოს keyboard accessible;
- verification code იყოს ექვსი მკაფიო cell ან ერთი input შესაბამისი masking-ით;
- ყველა success/error/expired state დაიდიზაინოს;
- auth გვერდებზე heavy WebGL არ ჩაიტვირთოს.

### Cabinet / compare

- cabinet: orders, addresses, wishlist და profile როგორც მკაფიო local navigation;
- compare: sticky first column, specs row groups, differences highlight და mobile horizontal scroll cue;
- no nested glass cards.

### Django Admin

- გამოიყენოს იგივე brand tokens და wordmark, მაგრამ დარჩეს dense/functional;
- WebGL, cinematic scroll და decorative motion admin-ში აკრძალულია;
- tables, filters, image preview, publication/verification states და bulk actions იყოს მთავარი.

## 13. Motion system

მოძრაობა იყოფა ოთხ დონედ:

1. **Signature** — WebGL hero და ერთი setup scene;
2. **Narrative** — section transitions, image masks, category preview;
3. **Commerce feedback** — selected variant, add-to-cart, drawer, validation;
4. **Ambient** — მხოლოდ waveform/signal line, ძალიან დაბალი ამპლიტუდით.

Timing:

- control feedback: 120–180 ms;
- drawer/menu: 260–360 ms;
- section reveal: 520–720 ms;
- signature transition: 700–1100 ms;
- stagger: 45–80 ms, მაქსიმუმ 6 item;

ერთი generic `.reveal` ყველა ელემენტზე აღარ გამოიყენოს. თითო სექციას ჰქონდეს საკუთარი choreography, მაგრამ ერთსა და იმავე easing/rhythm ოჯახში.

## 14. WebGL engineering requirements

- შეინარჩუნოს არსებული particle simulation და audio analyser contract;
- shader colors გადავიდეს uniform-ებად და theme/scene state-იდან იმართოს;
- desktop DPR cap: 1.5; mobile: 1.0–1.25;
- particle resolution: high 128, medium 96, low/mobile 64–80;
- `visibilitychange`-ზე და offscreen IntersectionObserver state-ზე animation loop pause/resume;
- average FPS-ის ვარდნისას ავტომატურად შეამციროს DPR/particle load;
- handle `webglcontextlost`/`webglcontextrestored`;
- `prefers-reduced-motion`-ზე არ გაეშვას მუდმივი particle loop; გამოჩნდეს generated/static poster;
- tab hidden-ზე audio შეიძლება გაგრძელდეს მხოლოდ user choice-ის მიხედვით, WebGL render კი უნდა გაჩერდეს;
- engine cleanup მეთოდი მოხსნას listeners, cancelAnimationFrame და media streams;
- hero არ უნდა შეაფერხოს search, nav, CTA ან screen reader structure.

## 15. Responsive წესები

- 320 px-ზე horizontal overflow არ შეიძლება;
- 360/390/430 px mobile, 768/1024 tablet, 1366/1440/1920 desktop სავალდებულო review widths;
- mobile-ზე WebGL composition გამარტივდეს, copy იყოს პირველი და product silhouette არ მოიჭრას;
- hover-only მოქმედება ყოველთვის ჰქონდეს touch-visible ალტერნატივა;
- custom cursor თუ დაემატება, მხოლოდ fine pointer-ზე და მხოლოდ media zones-ში გამოჩნდეს როგორც `VIEW`, `DRAG` ან `ZOOM` cue;
- Georgian, English და Russian ცალ-ცალკე screenshot review გაიაროს; ტექსტის სიგრძის გამო button/nav truncation არ დაიშვას.

## 16. Accessibility და reduced motion

- WCAG 2.2 AA;
- visible `:focus-visible` ყველა interactive control-ზე;
- 44×44 px target იქ, სადაც პრაქტიკულია;
- dialogs/drawers: focus trap, Escape close, opener-ზე focus restore;
- icon-only control-ს localized accessible name;
- player, gallery, carousel, variants და star rating სრულად keyboard-operable;
- async cart/rating/AI updates — `aria-live`;
- reduced motion: WebGL still, no smooth scroll, no parallax/tilt/scrub, video autoplay off, transitions ≤150 ms fade;
- color-only state აკრძალულია.

## 17. CSS/JS არქიტექტურა

Terra-მ redesign არ უნდა ჩაამატოს კიდევ ერთი დიდი patch-ად მიმდინარე `store.css`-ის ბოლოში.

რეკომენდებული source structure:

- `static/styles/_tokens.css`
- `static/styles/_base.css`
- `static/styles/_type.css`
- `static/styles/_shell.css`
- `static/styles/_components.css`
- `static/styles/_commerce.css`
- `static/styles/_home.css`
- `static/styles/_motion.css`
- `static/styles/_responsive.css`
- production bundle: `static/store.css`

JavaScript:

- `static/js/core-ui.js`
- `static/js/motion.js`
- `static/js/catalog.js`
- `static/js/product.js`
- `static/js/commerce.js`
- `static/js/guide.js`
- `static/hero3d/` უცვლელი module boundary-ით, მაგრამ optimized engine/player files-ით.

თუ build pipeline დაემატება, source files დარჩეს readable და compiled bundle reproducible. არცერთი external CDN runtime dependency არ დაემატოს.

## 18. განხორციელების ფაზები Terra-სთვის

### Phase 0 — Baseline and contract

- გადაიღოს screenshot-ები home, shop, product, bag, checkout, login, cabinet, compare-ზე 1440 და 390 px-ში;
- დააფიქსიროს მოქმედი selectors/endpoints/forms;
- შექმნას branch `redesign/terra-premium`;
- backend/models/migrations არ შეცვალოს დიზაინის მიზეზით.

**Gate:** ყველა მიმდინარე test ჯერ კიდევ მწვანეა.

### Phase 1 — Foundations

- ახალი tokens, typography, wordmark, grid, spacing, radii, focus და theme;
- ამოიღოს Inter, cyan/purple palette, generic background blob და default glass surfaces;
- განაახლოს `DESIGN.md` რეალურ სისტემაზე.

**Gate:** base shell ორივე theme-ში და სამივე ენაზე სწორია.

### Phase 2 — Global shell

- header, search, language/theme/account/bag controls, mobile nav, footer;
- buttons, fields, chips, alerts, dialogs, drawer grammar;
- unified experience dock skeleton.

**Gate:** keyboard navigation და 320 px overflow test.

### Phase 3 — Home cinematic experience

- WebGL re-grade/optimization;
- new hero composition;
- player/mic redesign;
- category atlas, video, product drop, setup scene, trust/footer choreography.

**Gate:** stable desktop/mobile FPS, reduced-motion fallback და mic/player states.

### Phase 4 — Catalog

- shop header/filter/sort/grid;
- new product card;
- responsive filters, pagination, empty/loading/error states.

**Gate:** search/filter/sort URLs და cart actions უცვლელად მუშაობს.

### Phase 5 — Product detail

- gallery/zoom/fullscreen, sticky purchase panel, variants, specs, rating/reviews, related products;
- shared image page transition და mobile purchase bar.

**Gate:** gallery keyboard/swipe, selected variant, price/stock/hidden input და add-to-cart regression tests.

### Phase 6 — Commerce and account flows

- cart drawer/bag, checkout, auth, verification/reset, cabinet, compare, success/error pages;
- transactional email visual templates light but brand-consistent.

**Gate:** full checkout/auth journey, no lost focus, all error states visible.

### Phase 7 — Motion polish

- add-to-bag flight, theme iris, section choreography, media cursor, view transitions;
- remove redundant/repetitive animation;
- clean z-index layers.

**Gate:** no animation blocks input, scroll or navigation.

### Phase 8 — Final QA

- Django checks/tests, static collection;
- Playwright smoke + visual screenshots;
- keyboard-only, reduced-motion, dark/light, KA/EN/RU;
- broken media, console errors, overflow, focus, loading and empty states;
- performance profiling with WebGL enabled.

## 19. Performance acceptance criteria

- Home Lighthouse Performance target: ≥80 mobile, ≥90 desktop;
- Shop/product/checkout target: ≥90 mobile;
- CLS ≤0.10;
- INP ≤200 ms;
- LCP shop/product ≤2.5 s, home ≤3.0 s on agreed test profile;
- WebGL: stable 50–60 FPS mid-range desktop, stable ≥30 FPS supported mobile;
- offscreen/hidden WebGL CPU/GPU activity მინიმუმამდე უნდა ჩამოვიდეს;
- product/card images მიიღებს intrinsic size, lazy loading და correct responsive sizes;
- motion libraries და 3D assets იყოს local, versioned და cacheable.

## 20. 10/10 შეფასების მატრიცა

| სფერო | ქულა |
|---|---:|
| ბრენდის უნიკალურობა და anti-AI character | 20 |
| ტიპოგრაფია, ფერი, hierarchy და spacing | 15 |
| რეალური პროდუქტის presentation | 15 |
| WebGL, 3D, scroll და micro-interactions | 15 |
| shop/PDP/cart/checkout usability | 15 |
| responsive და multilingual quality | 10 |
| accessibility | 5 |
| performance და robustness | 5 |
| **სულ** | **100** |

Release არ ჩაითვლება 10/10-ად, თუ:

- დარჩა cyan/magenta AI-tech palette;
- დაბრუნდა Inter, generic gradient text, repeated glass cards ან pill-everything;
- ერთი და იგივე reveal ყველა სექციაზეა;
- WebGL/mobile performance არასტაბილურია;
- პროდუქტის ფოტო, variant, rating, cart ან checkout ფუნქცია გაფუჭდა;
- reduced-motion, keyboard ან სამენოვანი layout არ მუშაობს;
- WOW ეფექტი ფარავს ფასს, CTA-ს ან პროდუქტს.

## 21. Terra-ს პირდაპირი სამუშაო ინსტრუქცია

Terra-მ ჯერ სრულად წაიკითხოს `PRODUCT.md`, `DESIGN.md` და ეს ფაილი. შემდეგ იმუშაოს Phase 0 → Phase 8 თანმიმდევრობით. ყოველი phase-ის შემდეგ გაუშვას შესაბამისი gate და მხოლოდ მწვანე შედეგის შემდეგ გადავიდეს შემდეგ ეტაპზე.

მთავარი გადაწყვეტილება: **ერთი unforgettable WebGL world + ორი ძლიერი 3D commerce moment + მშვიდი, უკიდურესად ზუსტი დანარჩენი interface.** NEXORA უნდა იყოს შთამბეჭდავი პირველ 10 წამში და მარტივი ყველა მომდევნო მოქმედებაში.
