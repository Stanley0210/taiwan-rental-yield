/* housing.js — 實價收益 / Yield Atlas
 *
 * One scrolling argument, in two depths.
 *
 *   SIMPLE (default)  - the finding, the number, where to look, and the caveat,
 *                       in language a person who has never heard of 實價登錄 can
 *                       follow. Five sections, no jargon, no method.
 *   ADVANCED          - adds the honesty ladder, the cost model with live
 *                       assumptions, the dead hypothesis, the sample-bias
 *                       measurements, and every negative result.
 *
 * The toggle sits top-right and persists. Simple is the default because most
 * visitors are not underwriters, and a page that opens on a residual-slope chart
 * has already lost them.
 *
 * Conventions (each pinned by a test):
 *   - Vanilla IIFE, zero dependencies, hand-rolled SVG built as strings.
 *   - Colours are ALWAYS var(--token), even in SVG fill/stroke. So the theme
 *     toggle needs no re-render; language and mode do.
 *   - Straight quotes only.
 *   - netYield() below is a TWIN of net_yield() in underwrite.py. If one moves,
 *     move the other, or the page will disagree with the file that made it.
 */
(function () {
  'use strict';

  var D = null;
  var LANG = 'zh';
  var MODE = 'simple';
  var state = { rung: null, district: null, type: null, q: '', sort: 'y', desc: false,
                asm: null, maxPrice: null, minYield: null, maxMrt: null, volCounty: null };

  var TYPES = ['住宅大樓', '華廈', '公寓'];
  var TYPE_EN = { '住宅大樓': 'Tower', '華廈': 'Mid-rise', '公寓': 'Walk-up' };

  // ── copy ──────────────────────────────────────────────────────────────
  var STR = {
    brand:      ['實價收益', 'Yield Atlas'],
    brandsub:   ['全臺灣', 'Taiwan'],
    en:         ['EN', '中文'],
    theme:      ['深色', 'Dark'],
    simple:     ['簡易', 'Simple'],
    advanced:   ['進階', 'Advanced'],
    advOnly:    ['進階', 'ADVANCED'],

    // ── hero: the FINDING first, the number second ──────────────────────
    // The number in this headline is coverage_pct, so it must not be typed here
    // as well: it read "二十分之一" against a measured 3.66% for months, and
    // national coverage is 3.83% -- one in twenty-six.
    heroH:     ['全臺灣近三年有成交紀錄的房子，%s 棟裡只有一棟算得出租金報酬率。',
                 'Of the buildings that sold in Taiwan in the last three years, a rental yield can be computed for one in %s.'],
    // This sentence used to say "only 6.22% of buildings have both on file",
    // which is the number AFTER this site's own filters. Both records exist for
    // 27.8%. The page's own waterfall splits the loss correctly (law 72.2pp,
    // ours 21.6pp) and the headline contradicted it — attributing to the law
    // what is mostly us. Stating both is the stronger version of the argument,
    // because separating them is the thing nobody else does.
    heroP:     ['要知道一間房子的租金報酬率，你需要同時知道它賣多少錢、租多少錢。政府的實價登錄兩件事都有記錄——但同一棟樓兩種紀錄都有的很少，而且有的那些，跟沒有的那些，根本不是同一種房子。',
                 'To know a building\'s rental yield you need both what it sold for and what it rents for. The public registry records both -- but few buildings have both on file, and the ones that do are not the same kind of building as the ones that don\'t.'],
    heroYield:  ['這 %s 棟的租金報酬率（未扣成本）', 'Gross yield across those %s buildings'],
    heroCov:    ['有成交紀錄的建物中，算得出報酬率的比例', 'Share of sold buildings where a yield is computable'],
    layExcl:    ['算不出來的建物', 'Buildings that cannot be priced'],
    exclLeg:    ['灰點　有成交也有租賃，但配不出報酬率',
                 'Grey  has both records, still cannot be priced'],
    numLeg:     ['數字　該區算得出報酬率的建物數',
                 'Number  buildings there with a computable yield'],
    rampLegC:   ['顏色　各縣市毛報酬率中位數（未扣成本）', 'Colour  median GROSS yield, by county'],
    rampLegD:   ['顏色　各行政區毛報酬率中位數（未扣成本）', 'Colour  median GROSS yield, by district'],
    rampLegB:   ['顏色　各建物毛報酬率（未扣成本）', 'Colour  GROSS yield, by building'],
    hint0:      ['點縣市 → 再點行政區 → 才看得到每一棟',
                 'Tap a county, then a district, then a building'],
    hint1:      ['點行政區看區內每一棟', 'Tap a district to see every building in it'],
    hint2:      ['點任一棟看明細', 'Tap any building for its detail'],
    backTo:     ['← 回 %s', '← back to %s'],
    backHome:   ['← 回全臺灣', '← back to Taiwan'],
    noCoordsB:  ['｜這 %s 棟畫不到地圖上（政府尚未公開該縣市門牌位置），請看下方表格',
                 '\u2502 these %s cannot be plotted — no public address-point file for this county yet. They are in the table below.'],
    noPairsB:   ['｜這一區沒有任何一棟房子同時登錄過買賣和出租，所以算不出報酬率',
                 '\u2502 no building here has both a sale and a lease on record, so no yield exists'],
    mapAria:    ['互動地圖：可用方向鍵移動、Enter 進入、Esc 返回',
                 'Interactive map. Arrow keys pan, Enter opens, Escape goes back.'],
    ariaMark:   ['%s，%s 棟，中位數 %s%', '%s, %s buildings, median %s%'],
    ariaMarkNo: ['%s，無資料', '%s, no data'],
    ariaBld:    ['%s，報酬率 %s%', '%s, yield %s%'],
    skipMap:    ['略過地圖', 'Skip the map'],
    msearch:    ['搜尋地址、行政區或縣市…', 'Search an address, district or county...'],
    msNone:     ['找不到', 'No match'],
    msBld:      ['棟', 'buildings'],
    incEy:      ['另一種看法', 'The same data, asked differently'],
    incH:       ['一間房子，等於幾年的所得？', 'A home, in years of income'],
    incP:       ['報酬率是給已經有錢的人看的數字。把同一批成交價換成「等於幾年的所得」，問的就是另一個人的問題了。分母是%s，分子是全部有成交紀錄的建物中位數總價 %s 元——不是本站算得出報酬率的那一小塊。那一塊的中位總價是 %s 元，低 %s%%，用它算會得到 %s 年而不是 %s 年。（那一塊每坪貴 %s%%，但坪數也小，兩者相抵；每坪那個比較的對象是「配不到的建物」，和這句的「全部建物」不是同一群，不能拿來對這句做加減。）',
                 'A yield is a number for someone who already has capital. The same sale prices, divided by what people earn, is the same data asked on behalf of someone who does not. The denominator is %s; the numerator is the median price across EVERY building with a recorded sale, NT$%s -- not the sliver this site can price, whose median is NT$%s, %s%% lower. Using the sliver would give %s years instead of %s. (That sliver is %s%% dearer per ping but also smaller, and the two cancel; the per-ping comparison is against the buildings this site CANNOT price, a different group from every building, so it does not add up against this sentence.)'],
    incElided:  ['其餘 %s 個縣市在進階模式', '%s more counties in advanced mode'],
    incUnit:    ['年的所得', 'years of income'],
    incNote:    ['分母是「所得收入者平均每人所得收入總計」（%s 年），不是家戶可支配所得——家戶的數字會比較小。兩個都是公開統計，這裡只做除法。',
                 'The denominator is average total income per INCOME EARNER (%s), not household disposable income — a household ratio would be smaller. Both are published statistics; this is only the division.'],
    wbEy:       ['同一棟樓裡面', 'Inside one building'],
    wbH:        ['傢俱加 %s%%，樓層加在房價上', 'Furniture adds %s%%. Height is added to the price.'],
    wbP:        ['把同一棟樓裡的紀錄拿來互相比較，地段、屋齡、型態、有沒有電梯就全部一樣了 —— 剩下的差別才是傢俱或樓層本身值多少。買賣和租賃兩邊都這樣算一次，才看得出高樓層的價值是被算進房價，還是被算進租金。',
                 'Compare records inside ONE building and location, age, type and lift are all held constant -- what is left is what the furniture or the floor is actually worth. Doing it on the sale side and the rent side separately is what shows whether height is paid for in the price or in the rent.'],
    wbFurn:     ['附傢俱的租金溢價', 'Furnished rent premium'],
    wbFloor:    ['每高一層樓的租金溢價', 'Rent premium per floor up'],
    wbFloorR:   ['每高一層，租金多', 'Rent, per floor up'],
    wbFloorS:   ['每高一層，房價多', 'Price, per floor up'],
    wbFloorGap: ['同一棟樓裡往上爬一層，房價貴 %s%（%s 棟有多樓層成交），租金只多 %s%（%s 棟有多樓層租約）——兩個斜率來自不同的建物集合，相減得到差距 %s 個百分點。高樓層的好處幾乎全部被算進房價，沒有進到租金裡，所以樓層越高，租金報酬率反而越低。要注意這一段是「同棟內部」比出來的，而捷運那一段是跨建物比較，而且那一節的結論已經撤回。兩者不是互相佐證——這一段才是站得住的那一個。',
                 'Climb one floor in the same building and the price is %s% higher (%s buildings with sales on several floors) while the rent is only %s% higher (%s buildings with leases on several floors) -- two slopes from different building sets, subtracted for a gap of %s points. Height is paid for almost entirely in the price and barely in the rent, so the yield falls as you go up. Note what this is NOT: it is measured inside one building, while the transit section compares different buildings -- and that section\'s conclusion has been withdrawn. The two do not corroborate each other; this is the one that stands.'],
    wbFurnN:    ['%s 棟樓同時有附傢俱與未附傢俱的租約', 'across %s buildings letting both furnished and unfurnished'],
    wbFloorSN:  ['%s 棟樓在 2 個以上不同樓層有成交紀錄',
                 'across %s buildings with sales on 2 or more different floors'],
    wbFloorN:   ['%s 棟樓有兩個以上不同樓層的租約', 'across %s buildings with leases on 2+ different floors'],
    wbFloorNote:['「高樓層比較貴」在同一棟樓裡幾乎量不到：每高一層只有 %s%%，二十層樓加起來也只有 %s%%。跨棟比較看到的樓層溢價，多半是新大樓本來就比較貴。',
                 'Within one building the "high floor costs more" premium is barely measurable: %s%% per floor, %s%% across twenty of them. The floor premium visible across buildings is mostly newer towers being dearer in the first place.'],
    mortEy:     ['借錢的成本', 'The cost of the money'],
    mortH:      ['放在一起看', 'Side by side'],
    // Descriptive, and deliberately so. Two published numbers next to each
    // other is analysis; telling anyone what to do about it is 投顧法 territory
    // and 不動產估價師法 §14 territory, and this project stays out of both.
    mortTwo:    ['第二個官方利率：內政部「本季新增購置住宅貸款平均利率」全國 %s%%（%s），比央行五大銀行的數字高——用它的話，差距是 %s 個百分點。本頁以央行數字為主，因為它是最常被引用的基準；兩個都放在這裡。',
                 'A second official rate: the MOI\'s national average on new house-purchase loans, %s%% (%s), higher than the Central Bank five-bank figure -- against it the gap is %s points. The Central Bank figure leads because it is the usual benchmark; both are here.'],
    mortP:      ['這 %s 棟房子扣掉稅、管理費、空置與修繕之後的中位數報酬率是 %s%。作為對照，%s是 %s%（%s，窗口末端的單月數字）。兩個都是公開數字，放在一起看而已——本頁不提供投資建議，也不對任何個別房屋估價。',
                 'After tax, management fees, vacancy and repairs, the median of these %s buildings returns %s%. For comparison, the %s was %s% (%s -- a single month at the end of the window). Both are published figures, placed side by side. This page gives no investment advice and values no individual property.'],
    mortGap:    ['低 %s 個百分點', '%s pp lower'],
    mortSame:   ['高 %s 個百分點', '%s pp higher'],
    // ── reference rates (v1.9) ── different denominators, never subtracted
    bmDep:      ['五大銀行一年期定存（固定，牌告）',
                 'Five-bank 1-year time deposit (fixed, posted)'],
    bmRed:      ['央行重貼現率', 'CBC rediscount rate'],
    bmMort:     ['五大銀行新承做購屋貸款',
                 'Five-bank new house-purchase loan rate'],
    bmLDep:     ['定存', 'deposit'],
    bmLRed:     ['重貼現', 'rediscount'],
    bmLMort:    ['房貸', 'mortgage'],
    bmSame:     ['五家相同', 'identical at all five'],
    bmSpread:   ['五家差距 %s 個百分點', 'spread across the five %s pp'],
    bmP:        ['同一頁上的四個數字，四個不同的分母：%s 棟建物扣掉模型成本（稅、管理費、空置、修繕）後的中位數淨報酬率 %s%%；五大銀行一年期定存牌告固定利率 %s%%（%s，%s）；央行重貼現率 %s%%（%s）；五大銀行新承做購屋貸款加權平均利率 %s%%（%s）。定存是稅前、保本、名目的利率；淨報酬率是扣掉估算成本、不保本的建物中位數。本頁把它們並排，不相減。',
                 'Four numbers on one page, four different denominators: the median net yield of %s buildings after modelled costs (tax, management, vacancy, repairs), %s%%; the one-year fixed time-deposit rate posted by the five major banks, %s%% (%s, %s); the central bank\'s rediscount rate, %s%% (%s); and the five banks\' weighted average rate on new house-purchase loans, %s%% (%s). A deposit rate is pre-tax, principal-guaranteed and nominal; the net yield is an after-modelled-cost building median with no guarantee. The page sets them side by side and does not subtract.'],
    bmLeg:      ['三條實線是三個對照利率：定存 %s%%、重貼現 %s%%、房貸 %s%%。它們的分母和報酬率不同，只標位置，不相減。',
                 'The three solid lines are three reference rates: deposit %s%%, rediscount %s%%, mortgage %s%%. Their denominators differ from that of the yield; they mark a position and are not subtracted.'],
    heroNet:    ['扣掉稅、管理費、空置、修繕之後', 'After tax, management, vacancy and repairs'],
    heroSocial: ['先講最重要的一件事：登錄裡已申報的整戶租約，%s%% 是政府的社會住宅包租代管，租金比市場低 %s%%。本站全部排除。這跟下一節「排除社會住宅只損失 %s 個百分點的建物」並不矛盾——那是按棟算，這是按租約算：社會住宅的租約集中在少數幾棟大型包租代管大樓裡，而一棟樓只要有一筆市場租約就留得下來。所以：這份租金資料，在篩掉社會住宅之前，主要量到的是社會住宅。',
                 'The most important thing first: of the whole-unit leases registered at all, %s%% are government social-housing sublease or management, renting %s%% below market. This site excludes every one. That does not contradict the next section\'s "removing social housing costs only %s points of buildings" -- that is counted by building, this by lease: social leases pile into a few large 包租代管 towers, and a building survives on a single market lease. So before it is filtered, this rent registry is mostly measuring social housing.'],
    heroCosts:  ['%s%% 背後的假設（切到進階模式可逐項調整）：房屋稅＋地價稅 %s%%／年（以成交價計）、管理費 %s 元／坪／月（有管理員者，臺北市；其他縣市套新北費率）、空置率 %s%%、修繕 %s%% 租金（隨屋齡加權）。',
                 'The assumptions behind %s%% (switch to advanced mode to adjust each one): holding tax %s%% of price per year, management NT$%s per 坪 per month where staffed (臺北市; other counties on New Taipei\'s rate), vacancy %s%%, repairs %s%% of rent scaled by age.'],
    heroCostsA: ['%s%% 背後的假設（可在下方調整）：房屋稅＋地價稅 %s%%／年（以成交價計）、管理費 %s 元／坪／月（有管理員者，臺北市；其他縣市套新北費率）、空置率 %s%%、修繕 %s%% 租金（隨屋齡加權）。',
                 'The assumptions behind %s%% (adjustable below): holding tax %s%% of price per year, management NT$%s per 坪 per month where staffed (臺北市; other counties on New Taipei\'s rate), vacancy %s%%, repairs %s%% of rent scaled by age.'],
    navAria:    ['顯示模式、語言與主題', 'Display mode, language and theme'],
    heroCeil:   ['完全不做品質篩選的上限', 'The ceiling, with no quality filters at all'],
    identWithin:['【識別強度】這一節的每個數字都是在「同一棟樓內部」比出來的：同一棟、同一批公設、同一個地段、同一個屋齡。地段、建商、屋齡這些干擾項是被結構消掉的，不是被假設掉的。這是本站證據強度最高的一類結果。',
                 '[Identification] Every number in this section is measured INSIDE a single building: same block, same common areas, same location, same age. Location, developer and age are held constant by construction, not by assumption. This is the strongest class of evidence on the site.'],
    identBetween:['【識別強度】這一節跟樓層那一節不同等級。這裡比的是「不同建物之間」——離站近的房子和離站遠的房子，在屋齡、坪數、建商、屋況、所在城市上全都不一樣，而這些差異一項都沒有被控制住。所以就算梯度成立，也只是相關性，不是因果。新北市與高雄市兩欄之所以要並列，就是為了把「城市」這個最大的干擾項固定住——而固定住之後，它就不成立了。',
                 '[Identification] This section is NOT the same class of evidence as the floor section. It compares DIFFERENT buildings: those near a station and those far from one also differ in age, size, developer, condition and city, and none of that is controlled for. So even where a gradient appears, it is a correlation, not a cause. The 新北市 and 高雄市 panels are there to hold the biggest confounder -- city -- constant. Held constant, it does not survive.'],
    heroBound:  ['三個數字，三道門檻。%s%% 的成交建物在登錄裡同時有買賣和租賃紀錄——但不限時間，一筆多年前的租約也算。要求租賃落在買賣前後四季內（否則配對沒有意義），剩 %s%%；這是不做任何品質判斷的上限。再套本站的品質條件，剩 %s%%。在四季這個配對窗之下，中間那個數字是上限。',
                 'Three numbers, three thresholds. %s%% of buildings with a sale also have a lease on file -- at any time, a lease from years earlier included. Require the lease to sit within four quarters of the sale, or the pair means nothing, and %s%% remain: the ceiling with no quality judgement at all. Apply this site\'s quality conditions and %s%% remain. Under a four-quarter pairing window, the middle number is the ceiling.'],
    ci95:       ['95%% 信賴區間 %s–%s%%', '95%% CI %s–%s%%'],
    // A gap between two yields is measured in percentage POINTS. Same interval,
    // different unit, and using the % form for it is a units error on a page
    // whose whole argument is about being careful with units.
    ciPP:       ['95%% 信賴區間 %s–%s pp', '95%% CI %s–%s pp'],
    pvVer:      ['版本 · 建置日 · commit', 'Version · built · commit'],
    pvSrc:      ['來源資料 SHA-256', 'Source data SHA-256'],
    pvFiles:    ['資料快照', 'Pinned snapshot'],
    pvFilesV:   ['%s 個季度 zip，共 %s MB，逐檔雜湊', '%s season zips, %s MB, hashed per file'],
    pvRepro:    ['重現方式', 'To reproduce'],
    pvReproV:   ['docs/REPRODUCING.md — 一行指令重建，並比對 housing_data.json.sha256',
                 'docs/REPRODUCING.md -- one command rebuilds it and checks housing_data.json.sha256'],
    pvCite:     ['v%s（%s）· 來源快照 %s', 'v%s (%s) · source snapshot %s'],
    pvPdf:      ['PDF 版', 'PDF'],
    pvSha:      ['資料雜湊', 'payload SHA-256'],

    sBuildings: ['配對建物', 'Buildings matched'],
    sPairs:    ['成交配對（同一棟內，一筆買賣 × 一筆租賃）',
                 'Sale × lease pairs, within one building'],
    sSeasons:   ['資料季度', 'Quarters of data'],
    sRecords:   ['清理後紀錄', 'Records after cleaning'],
    sUniverse:  ['有成交紀錄的建物', 'Buildings with a sale on record'],

    // ── presale (預售屋) ────────────────────────────
    preEy:      ['還沒蓋好的房子', 'Homes that do not exist yet'],
    preH:       ['預售屋貴 %s%%，但「扣掉時間後還剩多少」這件事，這份資料分不出來',
                 'Pre-sale costs %s%% more — and this data cannot say how much of that is the wait'],
    preLead:    ['登錄裡有 %s 戶預售屋，而它們一戶都算不出租金報酬率 —— 不是資料不夠，是房子還不存在，沒有人能租一間還沒蓋好的房子。這一整塊市場，本頁的頭條數字在原理上就看不到。',
                 'The registry holds %s pre-sale dwellings, and not one of them can ever have a rental yield. Not for want of data -- the building does not exist, and nobody rents a flat that has not been built. This whole segment of the market is invisible to the headline on this page, in principle rather than in practice.'],
    preGap:     ['跟真正蓋好、而且簽約當下屋齡兩年以內的成屋比 —— 同一個行政區、同一種建物型態、同一個「簽約季」—— 預售每坪貴 %s%。比預售廣告常見的說法小得多。',
                 'Against buildings that were genuinely finished when the price was agreed and under two years old at that point -- same district, same building type, same CONTRACT quarter -- pre-sale runs %s% dearer per ping. Far smaller than the premium pre-sale marketing implies.'],
    preLag:     ['把比較對象往後推，差距一路縮小到負的：兩年後預售反而比成屋便宜 %s%。但這不代表什麼。',
                 'Push the comparison forward in time and the gap turns negative -- at two years pre-sale is %s% cheaper than completed. That on its own means nothing.'],
    preLim:     ['一個必須說的陷阱：買賣資料裡的「交易年月日」是簽約日，不是交屋日。如果只用完工年份篩「屋齡兩年以內」，篩出來的九成其實是「還沒蓋好就先簽約、蓋好才登錄」的前一批預售 —— 那等於拿預售跟預售比。本頁改成用簽約日跟完工日相減，並要求屋齡不能是負的。其餘沒有控制的：哪些建案選擇走預售、規格與建材、建商的定價策略。資料只有 11 季，兩年是極限。每一格買賣雙方都至少 25 筆。',
                 'One trap worth naming: 交易年月日 in the sale file is the CONTRACT date, not the handover date. Filter for age under two years using the completion year alone and nine rows in ten turn out to be the previous pre-sale cohort -- contracts signed before the building existed, registering once it topped out -- which is pre-sale compared against pre-sale. This page subtracts the completion date from the contract date and requires the age to be positive. Still uncontrolled: which projects sell off-plan, specification and finish, and developer pricing strategy. Eleven quarters means two years is the reach. Every cell needs 25 transactions on both sides.'],
    // ── transaction volume (v1.9) ── counts, not yields; descriptive only
    volEy:      ['交易量', 'Transaction volume'],
    volH:       ['登錄的買賣與租賃筆數，依契約季', 'Registered sales and leases, by contract quarter'],
    volLead:    ['從 %s 到 %s，實價登錄上的成屋買賣（契約日在建物完成之後）在 %s 有 %s 筆，到 %s 只剩 %s 筆（%s%%）；預售契約從 %s 筆降到 %s 筆（%s%%，至 %s）；租賃登錄則從 %s 筆升到 %s 筆（至 %s）。三條線的終點季不同，各自標在括號裡。',
                 'From %s to %s, existing-home sales on the registry (contract signed after the building was completed) went from %s, when they stood at %s rows, to %s, when they were down to %s (%s%%); presale contracts fell from %s to %s (%s%%, by %s); registered leases rose from %s to %s (by %s). The three series bottom out in different quarters, each named in brackets.'],
    volHorizon: ['每一季都用同一把尺量：契約季 Q 的紀錄只在 Q 或 Q+1 季公布時才計入。成屋買賣約 %s%% 在期限內出現，落在期限外的多半只晚一季（第 2 季 %s%%），三季以上只有 %s%%；預售與租賃 100%% 在期限內。',
                 'Every quarter is measured with the same ruler: a row for contract quarter Q counts only if it was published in season Q or Q+1. About %s%% of existing-home sales arrive inside that horizon; most of what falls outside it is only one season late (%s%% at lag 2), and just %s%% arrives three or more seasons later. Presale and lease rows arrive 100%% inside it.'],
    volCensor:  ['%s 是最後一季，只有當季公布的紀錄（成屋約佔最終數的 %s%%、預售與租賃約 %s%%），圖上以灰色標示，不能與前幾季比較。',
                 '%s is the latest quarter and carries only same-season rows (about %s%% of where existing-home sales will end, about %s%% for presale and leases); it is greyed on the chart and cannot be compared with earlier quarters.'],
    volCensL:   ['未完整', 'incomplete'],
    volPresaleOrigin: ['成屋買賣排除了「契約日早於建築完成年月」的預售轉登記（全期間 %s 筆，佔清理後買賣的 %s%%）；這些契約多在兩三年前簽訂，無法按契約季計入這個視窗。',
                 'Existing-home sales exclude rows whose contract predates the completion date, presale units registering on handover (%s rows over the window, %s%% of cleaned sales); those contracts were signed two to three years earlier and cannot be dated inside this window.'],
    volEvents:  ['三個政策時點：① 新青安優化措施（行政院會 2024-06-27 通過：自住切結、一生一次）② 囤房稅 2.0 生效 2024-07-01 ③ 央行第七波信用管制 2024-09-19。三者落在同一個季度交界，資料無法區分任何一個的效果，本節只描述、不歸因。113Q2 本身是高峰，之後的下降有一部分是從高點回落。',
                 'Three policy dates: ① 新青安 tightening (Executive Yuan, 2024-06-27: owner-occupancy affidavit, once per lifetime) ② 囤房稅 2.0 in force 2024-07-01 ③ Central Bank credit controls, round seven, 2024-09-19. All three sit at the same quarter boundary; the data cannot separate any one of them, so this section describes and does not attribute. 113Q2 is itself a peak, so part of the fall is reversion from a high.'],
    volEv1:     ['① 新青安優化 2024-06-27', '① 新青安 tightening 2024-06-27'],
    volEv2:     ['② 囤房稅 2.0 2024-07-01', '② 囤房稅 2.0 2024-07-01'],
    volEv3:     ['③ 央行第七波 2024-09-19', '③ CBC round 7 2024-09-19'],
    volAll:     ['全國', 'All Taiwan'],
    volFigA:    ['實價登錄筆數，依契約季', 'Registry rows by contract quarter'],
    volFigASub: ['三個登錄檔各自的單位：成屋＝買賣檔一筆交易；預售＝預售檔一份契約；租賃＝租賃檔一份租約。三列各有自己的尺度，不相加、不相除。這是本頁唯一不以「棟」計的章節：交易筆數不是報酬率。',
                 'Three files, three units: existing = one transaction row in the sale file; presale = one contract in the presale file; leases = one lease in the rental file. Each band has its own scale; they are neither summed nor divided. The one section on this page not counted in buildings: a transaction count is not a yield.'],
    volSerE:    ['成屋買賣（筆）', 'Existing-home sales (rows)'],
    volSerP:    ['預售契約（筆）', 'Presale contracts (rows)'],
    volSerL:    ['租賃登錄（筆）', 'Leases (rows)'],
    volXCon:    ['橫軸：契約季', 'x-axis: contract quarter'],
    volXReg:    ['橫軸：登記季', 'x-axis: registration quarter'],
    volFigB:    ['內政部 建物買賣移轉登記棟數', 'MOI building sale transfers registered'],
    volFigBSub: ['單位是「棟」、按登記季而非契約季、含所有用途與透天；與上圖並列、不相除。%s 全國 %s 棟。',
                 'Unit is 棟 (buildings), by registration quarter not contract quarter, all uses including 透天. Set beside the chart above, never divided. %s national: %s 棟.'],
    volNoRatio: ['為什麼不算「登錄率」：上圖數的是清理後的住宅交易筆數，下圖數的是登記的建物棟數；一筆交易可以是好幾棟，也可以是一棟的一部分。',
                 'Why there is no coverage ratio: the chart above counts cleaned residential transaction rows, the one below counts registered buildings; one transaction can be several buildings or a fraction of one.'],
    volLag:     ['官方棟數的下降晚一季出現（113Q3 %s 棟、113Q4 %s 棟、114Q1 %s 棟）。可能的原因是登記日晚於契約日（法定 30 日內登記），本頁未量測。',
                 'The official count falls a quarter later (113Q3 %s, 113Q4 %s, 114Q1 %s 棟). A possible reason is that registration follows the contract (the statutory window is 30 days); not measured here.'],
    volTblH:    ['逐季數字', 'Quarter by quarter'],
    volTblQ:    ['契約季', 'Contract quarter'],
    volTblO:    ['官方買賣移轉（棟，登記季）', 'Official sale transfers (棟, registration quarter)'],
    volCaptured: ['固定觀察期在各完整季捕捉到成屋買賣最終數的 %s%% 到 %s%%；期限之外的紀錄不計入，所以每一季少算的比例相近。',
                 'The fixed horizon captures %s%% to %s%% of each complete quarter\'s eventual existing-home rows; rows outside it are never counted, so every quarter is undercounted by a similar share.'],
    volLim:     ['這一節是筆數的描述，不是報酬率，也不是任何政策的效果估計。筆數會隨資料清理規則變動；規則與本頁其他章節相同（見方法）。',
                 'This section describes counts. It is not a yield and not an estimate of any policy\'s effect. Counts move with the cleaning rules, which are the same ones used everywhere on this page (see Method).'],
    prePlac:   ['因為把同樣的位移套在兩組成屋之間——那裡沒有交屋等待——差距也掉了幾乎一樣多（兩年掉 %s 個百分點）。價差會收斂只是因為房價在漲，任何隔著時間的比較都會這樣。所以本站的結論是：這份資料分不出「交屋等待」和「房價上漲」哪一個在解釋這個差距。唯一站得住的數字是對照真正蓋好的房子時的 %s%%（95%% 信賴區間 %s–%s）。',
                 'Because running the same shift between two completed groups -- where no delivery wait exists -- moves it almost as far (down %s points at two years). Gaps converge across time because prices rise, which every time-separated comparison does. So this site\'s conclusion is that this data cannot tell the delivery wait apart from the rising market. The one figure that stands is the %s%% gap against genuinely completed homes (95%% CI %s-%s).'],
    prePlacAdv: ['方法細節：把兩條曲線相除得到的「淨溢價」在五個時間落差上是 %s%%。在落差為零時它就是 %s%%——那裡沒有時間可以扣——而最遠那一格（%s%%）格子數最少、沒有信賴區間。本站早期只報了最遠那一格，已改正。',
                 'Method detail: dividing one curve by the other gives a "net premium" of %s%% across the five lags. At zero lag it is %s%% -- nothing to net out -- and the furthest cell (%s%%) is the sparsest, with no interval. An early version of this site reported only that furthest cell; corrected.'],
    prePlacL:   ['同期成屋之間（無交屋等待）',
                 'completed vs completed (no delivery wait)'],
    preReach:   ['涵蓋範圍要講清楚：這個比較只到得了 %s 戶（全部的 %s%）、%s 個行政區（共 %s 個）、%s 個格子。很多行政區沒有足夠的「真的蓋好的新成屋」可以對照。把每格門檻放寬到 5 筆或收緊到 100 筆，答案都還是 %s% —— 這一點是穩的。',
                 'The reach, stated plainly: this comparison touches %s dwellings (%s% of them), %s of %s districts, and %s cells. Many districts simply have too few genuinely-completed new builds to compare against. Loosening the per-cell floor to 5 or tightening it to 100 leaves the answer at %s% either way, so that much is stable.'],
    preX:       ['比較對象往後推 · 中括號是 95% 信賴區間（以行政區×型態為單位重抽）',
                 'completed comparison pushed forward · brackets are 95% CIs, bootstrapped over district x type clusters'],
    preNow:     ['同一季', 'same quarter'],
    preYr:      ['+%s 年', '+%s yr'],
    preUnits:   ['戶預售屋', 'pre-sale dwellings'],
    preProj:    ['個建案', 'projects'],
    preNoYield: ['算得出報酬率的', 'can have a yield'],

    // ── auction (金拍) ──────────────────────────────
    aucEy:      ['另一個管道', 'The other channel'],
    aucH:       ['拍賣掉的房子，這份資料大多看不到', 'This dataset mostly cannot see a home sold at auction'],
    aucP:       ['金拍是銀行透過台灣金服處分抵押品的管道，跟法院的法拍不是同一件事，規模也小得多。這一段講的全部是金拍。',
                 'This is 金拍 -- a bank disposing of collateral through TFASC -- and not 法拍, the court auction. They are different channels and this one is much smaller. Everything below describes 金拍 only.'],
    aucRes:     ['%s 筆裡只有 %s 筆賣得比底價高。其餘的都是剛好用底價成交 —— 一場拍賣只要有一個合格出價，就是以底價賣出。所以這個數字讀的是「有沒有第二個人來搶」，不是「便宜多少」。',
                 'Of %s lots, %s sold above the reserve. The rest cleared exactly at it -- an auction with a single qualifying bid sells AT the reserve. So this number reads as whether a second bidder turned up, not as how cheap the property was.'],
    aucReg:     ['這 %s 筆拍定紀錄（分屬 %s 棟建物）裡，只有 %s% 對得上本頁用來算報酬率的那份成交資料。拍賣掉的房子是真的換了手，但它多半不在這個網站算得出數字的那個範圍內 —— 這是本頁一直在講的同一件事，換一個管道再看一次。（比對的是清理後的買賣資料：住宅、整戶、排除親友交易。沒對上不代表實價登錄完全沒有這棟樓的紀錄。）',
                 'Of the %s auction lots here — %s buildings between them — %s% match the cleaned sale data this page computes its yields from. An auctioned home really did change hands, and mostly it sits outside the slice this site can measure -- the same argument as the rest of the page, seen down a different channel. (Matched against cleaned sales: residential, whole dwellings, arms-length. A miss does not prove the raw registry holds nothing for that building.)'],
    // The old copy assigned a magnitude ("a lot of") to a discount this page
    // explicitly declines to measure -- aucNote says no price-per-ping is
    // computed and no market comparison is made. No reserve level is stored
    // either, so the claim had nothing behind it.
    aucRound:   ['沒賣掉的會降價重拍。能量到的只有這件事：第一輪清掉底價的比例是 %s%%（n=%s），到第三、四輪變成 %s%%（n=%s）與 %s%%（n=%s）——但那兩輪加起來只有 %s 筆，占全部的 %s%%，而且就算在那裡，得標價也只比底價高約 %s%%。本頁不計算拍賣折價幅度，所以也不宣稱這張時間表解釋了其中多少。（第二輪筆數不足 10 筆，未顯示。）',
                 'Unsold lots are re-listed at a lower reserve. What can be measured is only this: the share clearing above reserve runs %s%% in round 1 (n=%s) and %s%% (n=%s) and %s%% (n=%s) in rounds 3 and 4 -- but those two rounds are %s lots between them, %s%% of the total, and even there the winning bid clears about %s%% over reserve. This page does not compute an auction discount, so it makes no claim about how much of one this schedule accounts for. (Round 2 has fewer than 10 lots and is not shown.)'],
    aucNote:    ['資料來源：台灣金融資產服務股份有限公司公開標售結果，%s 至 %s，共 %s 個場次。只計入有門牌的建物，土地標的不算。這份資料沒有任何面積欄位，所以本站不計算拍賣的每坪單價，也不與市價相比。',
                 'Source: TFASC published auction results, %s to %s, across %s sessions. Buildings with a street address only; land parcels are excluded. The feed carries no floor area at all, so no price-per-ping is computed here and no comparison against market prices is made.'],
    aucRoundL:  ['第 %s 拍', 'Round %s'],
    aucAbove:   ['高於底價成交', 'sold above reserve'],
    aucInReg:   ['在本頁的成交資料裡', 'in this cleaned sale data'],

    // ── distance to MRT ─────────────────────────────────────────────────
    mrtEy:      ['捷運與報酬率', 'Transit and yield'],
    mrtH:       ['離捷運越遠，報酬率越高', 'The further from the MRT, the higher the yield'],
    // Used when the gradient does not survive holding city constant. The old
    // heading asserts a transit effect that the Taipei panel cannot support, and
    // a heading that contradicts its own body is worse than either alone.
    mrtH2:      ['「離捷運越遠報酬率越高」——這個結論撐不住',
                 '"The further from the MRT, the higher the yield" -- this one does not hold'],
    mrtP:       ['全部捷運城市合起來看：離最近車站 250 公尺以內的房子，中位數報酬率是 %s；兩公里半以上的是 %s。房價與租金都隨距離下降——房價 %s%%、租金 %s%%。這是第一張圖顯示的東西。這一節其餘的部分，是在檢驗它站不站得住——結論是站不住。',
                 'Across every metro city together: within 250 m of a station the median yield is %s; beyond 2.5 km it is %s. Both price and rent fall with distance -- price by %s%%, rent by %s%%. That is what the first panel shows. The rest of this section tests whether it survives -- and it does not.'],
    mrtAll:     ['全部捷運城市', 'All MRT cities'],
    mrtDefn:    ['在 %s，把「捷運站」的定義從「僅重軌」改成「含輕軌」，同一批建物、同一套算法，結果就從 %s pp（%s）變成 %s pp（%s）。原因不神秘：淡海輕軌服務的正是原本被歸為「遠」的淡水一帶，多了那條線，那些房子就變成「近」的了。這不是一個關於捷運的發現，是一個關於「你決定什麼算車站」的發現。',
                 'In %s, change what counts as a station -- heavy rail only, or heavy rail plus 輕軌 -- and the same buildings under the same method go from %s pp (%s) to %s pp (%s). The reason is not mysterious: 淡海輕軌 serves the outer 淡水 area that WAS the far group, so adding that line reclassifies those buildings as near. This is not a finding about transit. It is a finding about where you draw the line.'],
    mrtRep:     ['更關鍵的是獨立複製。高雄有自己的捷運系統，是在本站宣稱這個結論之後才進得了資料的——在那裡，最近段 %s%% 與最遠段 %s%% 的差距是 %s pp（%s），兩種車站定義下都一樣。一個在新北市靠某個定義才成立、在高雄完全不成立的梯度，不能當成發現發布。',
                 'The replication matters more. 高雄 has its own metro and only entered this dataset after the claim was made. There the nearest band (%s%%) and the furthest (%s%%) differ by %s pp (%s) -- under both station definitions. A gradient that needs one definition to appear in 新北市 and is absent in 高雄 is not something to publish as a finding.'],
    mrtVerdict: ['【撤回】把全國車站補齊、兩種車站定義都跑、並在高雄獨立複製之後，結論是：這份資料支持不了「離捷運越遠報酬率越高」這個說法。距離與報酬率之間看得到的關係，小於「你怎麼定義車站」造成的差異。四張圖留著，因為它們就是證據。',
                 '[Withdrawn] With the national stations in, both station definitions run, and 高雄 as an independent replication, the conclusion is that this data does not support the claim that yields rise with distance from the MRT. Whatever relationship is visible is smaller than the difference made by deciding what a station is. All four panels stay, because they are the evidence.'],
    mrtSumSpread:['最遠段 − 最近段', 'furthest − nearest'],
    mrtSumCI:   ['兩端的信賴區間', 'the two intervals'],
    mrtSep:     ['區間分得開', 'intervals separate'],
    mrtOv:      ['區間重疊', 'intervals overlap'],
    mrtHist:    ['這一節的紀錄：第一版用只有臺北 131 站的圖層算全國距離，高雄的房子被算成離車站 275 公里；第二版用臺北市檢驗說效果消失，但臺北市 2.5 公里外只有 4 棟；第三版用只含重軌的定義說效果成立。三次都在補齊資料後被推翻。現在的版本是把全國車站補齊、兩種定義都跑、在高雄獨立複製之後的結果。',
                 'This section\'s record: v1 computed national distances from a 131-station Taipei-only layer, so Kaohsiung homes sat 275 km from a station; v2 tested 臺北市 and called the effect gone, but Taipei has 4 buildings beyond 2.5 km; v3 called it real on heavy rail alone. Each was overturned by better data. What stands now is the result after the national stations went in, both definitions ran, and 高雄 replicated independently.'],
    mrtHeavyL:  ['僅重軌（不含輕軌）', 'Heavy rail only (no 輕軌)'],
    mrtRepL:    ['高雄市（獨立複製）', '高雄市 — independent replication'],
    mrtCtl:     ['新北市，含輕軌（唯一近端與遠端樣本都夠的縣市）',
                 '新北市, light rail included — the one county with both a real near and far group'],
    // "MRT cities only" was not true of the data: every building got a distance,
    // including ones hundreds of kilometres from the layer's nearest station.
    mrtN:      ['車站圖層來自 OpenStreetMap，涵蓋全臺的捷運與輕軌（%s 站）。只保留最近車站在 15 公里以內的 %s 棟（占可配對建物的 %s）——臺南沒有捷運，所以整個排除。距離為直線距離，不是步行距離。每格至少 25 棟才顯示。',
                 'The station layer is OpenStreetMap, every metro and light-rail station in Taiwan (%s stations). Only the %s buildings whose nearest station is within 15 km are kept (%s of the matched set); 臺南 has no metro and is excluded outright. Straight-line, not walking distance. Bins under 25 buildings are not shown.'],
    mrtBin:     ['距離最近車站', 'Distance to nearest station'],
    mrtYield:   ['中位數報酬率', 'Median yield'],
    mrtPrice:   ['中位數房價', 'Median price'],

    // ── coverage ────────────────────────────────────────────────────────
    covEy:      ['看得見與看不見', 'Seen and unseen'],
    covH:       ['老公寓幾乎全部消失', 'Walk-ups almost entirely vanish'],
    covP:       ['一棟房子要同時被賣掉、又剛好被登錄出租，才算得出報酬率。電梯大樓有 %s 做得到；五層樓老公寓只有 %s。老公寓佔全部成交建物的 %s%%，但在算得出報酬率的名單裡，它們只剩 %s%%。',
                 'A building needs both a recorded sale and a recorded lease before a yield exists. That happens for %s of towers and %s of walk-ups. Walk-ups are %s%% of the housing that sells -- and %s%% of the housing you can measure.'],
    covRate:    ['可配對比例', 'Match rate'],
    // This labelled the FINAL match rate (after every filter) as the
    // both-records share, which is the waterfall's step 0 and 3x larger.
    covRateS:   ['算得出報酬率的建物比例', 'Share of buildings where a yield can be computed'],
    covMix:     ['房屋結構 vs 看得見的結構', 'The stock vs the visible slice'],
    covMixS:    ['左：所有有成交紀錄的建物。右：能算出報酬率的建物。',
                 'Left: all buildings with a recorded sale. Right: buildings where a yield is computable.'],
    // NOT "all housing stock": this column is the 4+ storey part the site's
    // filter can contain, renormalised to 100. 1-3 storey (42.7% of everything)
    // is stated in the caption, not drawn. Labelling it "all" put 住宅大樓 at
    // 42% where its share of ALL stock is 24%.
    covStock:   ['住宅存量（4 層以上）', 'Housing stock, 4+ storeys'],
    covMixS3:   ['左：全臺灣 4 層以上的住宅存量（房屋稅籍，以宅計，依樓層對應到三種型態；1–3 層另計，見下文）。中：所有有成交紀錄的建物。右：能算出報酬率的建物。',
                 'Left: Taiwan\'s housing stock of 4+ storeys (house-tax roll, in units, floor bands mapped to the three types; 1-3 storeys stated below, not drawn). Middle: every building with a recorded sale. Right: buildings where a yield is computable.'],
    covStockP:  ['對照真正的存量，而不只是「有賣過的」：在本站篩選條件涵蓋得到的住宅裡，電梯大樓佔 %s%%，但在算得出報酬率的建物裡佔 %s%%；老公寓佔 %s%%，算得出來的只剩 %s%%。而全國還有 %s%% 的住宅是一到三層的透天，本站的篩選在定義上就看不到。左欄是以「宅」計、右欄是以「棟」計——一棟大樓有幾十戶、一棟公寓只有幾戶，所以左欄已經比按棟計偏向大樓了；即使如此，落差還是這麼大。',
                 'Against the real stock, not just what sold: of the housing this site\'s filters can contain, towers are %s%% of units but %s%% of the buildings a yield can be computed for; walk-ups are %s%% of units and %s%% of what can be priced. And %s%% of all dwellings are 1-3 storey 透天 this site\'s filter cannot see by construction. The left column counts units and the right counts buildings -- a tower is dozens of units, a walk-up a handful -- so the left is already tilted toward towers relative to a building count. The gap is still this large.'],
    covStockN:  ['住宅存量：內政部房屋稅籍住宅類數量，%s。11 層以上對應住宅大樓，6–10 層對應華廈，4–5 層對應公寓。',
                 'Housing stock: MOI house-tax roll, residential class, %s. 11+ storeys mapped to 住宅大樓, 6-10 to 華廈, 4-5 to 公寓.'],
    ageStockT:  ['全國住宅平均屋齡 %s 年，本站配對建物中位數 %s 年', 'Taiwan\'s stock averages %s years old; this site\'s matched buildings have a median age of %s'],
    ageStockS:  ['實心＝全國住宅存量的屋齡分布（房屋稅籍）；外框＝本站配對建物的分布。每列右側為兩者比例。',
                 'Filled = age distribution of all housing stock (house-tax roll); outline = this site\'s matched buildings. Percentages at right are stock / ours.'],
    ageStockP:  ['臺灣有 %s%% 的住宅超過四十年，本站算得出報酬率的建物裡只有 %s%% 那麼老。反過來，十年內的新屋佔存量 %s%%，卻佔本站配對建物的 %s%%。把本頁的核心發現對照真正的分母，結果一樣：算得出報酬率的房子，是新的那一群。',
                 '%s%% of Taiwan\'s homes are over forty years old; %s%% of the buildings this site can price are. The other way round, homes under ten years old are %s%% of the stock and %s%% of the matched set. Set the page\'s central finding against the real denominator and it holds: the homes a yield can be computed for are the new ones.'],
    covAll:     ['所有成交建物', 'All sold buildings'],
    covMatched: ['可配對建物', 'Matched buildings'],
    ageT:       ['再對照登錄內部：算得出來的房子，比賣過但配不到的年輕 %s 年', 'And against the registry\'s own unmatched: the ones you can measure are %s years newer'],
    ageS:       ['建築完成年（民國）中位數', 'Median year of completion (ROC calendar)'],
    ageMatched: ['可配對', 'Matched'],
    ageUn:      ['無法配對', 'Not matched'],
    wfH:        ['看不見的 %s%%，有多少是法規、有多少是我們自己篩掉的', 'Of the %s%% you cannot see, how much is the law and how much is us'],
    wfP:       ['把「看不見」全部推給法規是不誠實的，但把它推給本站也是。實際拆開：%s 個百分點的建物在登錄裡根本沒有租約——多數是自住，其餘是出租但沒有申報（法律只要求房仲與包租業成交的租約登錄），資料分不出這兩種。這一項不是本站的選擇。我們自己的 %s 道篩選再吃掉 %s 個百分點——這才是本站的。',
                 'Blaming all of the invisibility on the law would be dishonest, and so would blaming it on this site. Split it: %s points are buildings with no lease on file at all -- most owner-occupied, the rest let but never registered (only agency- and operator-handled leases must be), and the data cannot tell which. That part is not this site\'s choice. Our own %s filters cost a further %s points -- that part is.'],
    wfLaw:     ['登錄裡沒有租約（自住，或出租但未申報）',
                 'no lease on file (owner-occupied, or let but unregistered)'],
    wfOurs:     ['我們的篩選', 'our filters'],
    wfCeil:     ['完全不篩選、只保留 4 季配對窗，上限也只有 %s%%。',
                 'With no filters at all and only the 4-quarter window, the ceiling is still %s%%.'],
    priceT:     ['而且貴 %s%%', 'And %s%% more expensive'],
    priceS:     ['每坪成交價中位數。這是報酬率的分母，所以差距會直接、可計算地偏移結果。',
                 'Median price per ping. This is the yield denominator, so a gap here biases the headline mechanically and by a computable amount.'],

    psEy:       ['修正選擇偏誤', 'Correcting the bias'],
    psH:        ['把樣本加權回真實的房屋結構', 'Reweighting the sample back to the actual stock'],
    psP:        ['量到偏誤卻不修正，等於要讀者自己猜它有多大。這裡用價格十分位加建物型態做事後分層加權，把 %s 棟配對建物加權回全部 %s 棟成交建物的組成。可見樣本嚴重偏向高價建物——最貴的十分之一在配對樣本裡佔 %s%%，實際只佔 10%%——而價格正是分母，所以可見的報酬率是偏低的。',
                 'Measuring a bias and not correcting it leaves the reader to guess its size. Post-stratifying on price decile and building type reweights the %s matched buildings to the composition of all %s that sold. The visible sample leans heavily to expensive buildings -- the top tenth is %s%% of it against 10%% of the stock -- and price is the denominator, so the visible yield reads low.'],
    psVis:      ['可見樣本', 'Visible sample'],
    psAdj:      ['加權後', 'Reweighted'],
    psByType:   ['只用建物型態加權', 'Reweighted by type only'],
    psNote:     ['拆開來看：只用建物型態加權移動 %s pp，只用價格分位加權移動 %s pp，兩者一起是 %s pp。價格是主要那一項——它是報酬率的分母，而可見樣本嚴重偏向貴的建物——但型態並非可以忽略。',
                 'Split out: reweighting by type alone moves it %s pp, by price decile alone %s pp, and by both %s pp. Price is the larger term -- it is the yield\'s denominator and the visible sample leans hard to expensive buildings -- but type is not negligible.'],
    psDecile:   ['價格十分位：樣本 vs 實際', 'Price decile: sample vs stock'],

    ciNote:     ['橫線是中位數的 95%% 信賴區間（對建物、再對配對做兩層拔靴法）。%s 組相鄰行政區的區間互相重疊（共 %s 組）——也就是說這個排名的大部分名次，統計上分不出來。頭尾兩端則確實不同。',
                 'The line is a 95%% confidence interval on the median (two-stage bootstrap, over buildings then over pairs within each). %s of %s adjacent pairs of districts have overlapping intervals -- most of this ranking is not statistically distinguishable. The two extremes genuinely are.'],
    ciNoteCty:  ['橫線是中位數的 95%% 信賴區間。在縣市這一層，%s 組相鄰縣市的區間重疊（共 %s 組），只有 %s 分得開。點任一個縣市展開它的行政區——行政區那一層的重疊更嚴重。',
                 'The line is a 95%% confidence interval on the median. At county level %s of %s adjacent pairs overlap; only %s separate. Click a county to open its districts -- the overlap is worse one level down.'],
    ciNoteAll:  ['橫線是中位數的 95%% 信賴區間（對建物、再對配對做兩層拔靴法）。全部 %s 組相鄰行政區的區間都互相重疊——**這個排名裡沒有任何一組相鄰名次在統計上分得出來**。只有距離夠遠的兩端才真的不同：最低的 %s 是 %s，最高的 %s 是 %s，兩者不重疊。把這張圖當成分佈看，不要當成名次看。',
                 'The line is a 95%% confidence interval on the median (two-stage bootstrap, over buildings then over pairs within each). ALL %s adjacent pairs of districts overlap -- **no neighbouring position in this ranking is statistically distinguishable.** Only the far ends genuinely differ: the lowest, %s, at %s, against the highest, %s, at %s, which do not overlap. Read this as a distribution, not as a league table.'],
    vbNote:     ['空置率的問題：%s%s 排第一，但我們對每一區都套用同樣的 %s%% 空置率。要讓它掉到中位數，它的空置率得高到 %s%%。區級的空屋統計自民國 109 年起停產，無法逐區帶入真值；縣市級的還在，放在下面「對照官方數字」那一節——%s是 %s%%，而 %s%% 是個很高的門檻。',
                 'A vacancy caveat: %s%s ranks first, but every district is charged the same %s%% vacancy. To drop it to the median its vacancy would have to reach %s%%. District-level empty-home statistics stopped in ROC 109, so no per-district rate can be wired in; the county series continues and sits in the official-figures section below -- %s is %s%%, and %s%% is a high bar to clear.'],

    dispEy:     ['同一棟樓裡面', 'Inside one building'],
    dispH:      ['同一棟樓的差距，比行政區之間還大 %s 倍', 'One building spreads %sx wider than the whole city'],
    dispP:      ['在有 4 筆以上配對的 %s 棟建物裡，同一棟樓內部的報酬率四分位距中位數是 %s 個百分點；而 %s 個行政區的中位數彼此之間，四分位距只有 %s 個百分點。也就是說：你隨機挑同一棟樓的兩戶，報酬率差距預期會比隨機挑兩個行政區還大。這直接讓「行政區平均值」——也就是市面上所有同類產品賣的東西——失去意義。',
                 'Across the %s buildings with 4 or more pairs, the median spread of yields INSIDE a single building is %s pp. Across %s district medians, the spread is %s pp. Two units picked at random from one building differ more than two districts do. That is what makes a district average -- the product every competitor sells -- close to meaningless.'],
    dispHN:     ['同一棟樓的內部差距，是行政區之間的 %s 分之一', 'Between districts spreads %sx wider than one building'],
    dispPN:     ['在有 4 筆以上配對的 %s 棟建物裡，同一棟樓內部的報酬率四分位距中位數是 %s 個百分點；%s 個行政區的中位數彼此之間，四分位距是 %s 個百分點。在全國尺度上，地段之間的差距比較大——這很合理，因為 22 個縣市涵蓋的差異遠大於臺北市 12 個行政區。但同棟內部 %s 個百分點的離散度並沒有消失：它代表「某棟樓的報酬率」這句話本身就帶著相當的不確定性，也是本頁這個排名裡每一個中位數都附信賴區間的原因。',
                 'Across the %s buildings with 4 or more pairs, the median spread of yields INSIDE a single building is %s pp; across %s district medians it is %s pp. At national scale location dominates -- which is what you would expect, since 22 counties span far more than 12 Taipei districts. But %s pp of within-building spread does not go away: it means "the yield of that building" is itself an uncertain statement, and it is why every median in this ranking carries an interval.'],
    dispFix:    ['已更正：本站原本在這裡宣稱「同一棟樓的差距比行政區之間還大」。那是在只涵蓋雙北時量到的，改成全國之後方向就反了，而這段文字沒有跟著改。現在這段敘述由比值決定，不再寫死。',
                 'Corrected: this section used to claim that one building spreads wider than the whole city. That was measured on Taipei and New Taipei only; going national inverts it, and the copy did not follow. The claim is now derived from the ratio rather than asserted.'],
    dispWithin: ['同一棟樓內部（四分位距中位數）', 'Within one building (median IQR)'],
    dispBetween:['行政區之間（四分位距）', 'Between districts (IQR)'],

    repEy:      ['修繕設定', 'Repairs specification'],
    repH:       ['換一種修繕假設，結論會不會變？', 'Does the conclusion survive the other repair spec?'],
    // No count in the heading: the body's figure is counties that actually have
    // matched buildings (18), not the site's 22-county scope, and two different
    // numbers three lines apart just makes the reader stop.
    mgxH:       ['管理費：一個只有雙北來源的假設，套用到全國',
                 'Management fee: a two-city assumption charged nationwide'],
    mgxP:       ['管理費的公開調查只涵蓋臺北市與新北市。本站已擴及全國，其中 %s 棟「有管理員」的建物位於雙北以外的 %s 個縣市，卻一律被收取新北的費率——不是因為那是對的，是因為找不到分縣市的統計。它們佔全部配對建物的 %s%%。無法修正的假設就把它量出來：以下是把該費率減半、以及歸零之後的淨報酬率中位數。',
                 'The published management-fee surveys cover 臺北市 and 新北市 and nowhere else. The site now covers the country, so the %s buildings with on-site staff across the other %s counties are all charged New Taipei\'s rate -- not because it is right, but because no per-county statistic exists. They are %s%% of all matched buildings. An assumption that cannot be corrected gets measured instead: the median net yield with that rate halved, and removed.'],
    mgxBase:    ['目前假設（新北費率）', 'As charged now (New Taipei rate)'],
    mgxHalf:    ['其餘縣市費率減半', 'Rate halved outside 北北'],
    mgxZero:    ['其餘縣市不收管理費', 'No fee outside 北北'],
    mgxNote:    ['這不是一個修正，是一個曝險。真實的數字落在這兩端之間，而本站沒有資料可以指出落在哪裡。引用淨報酬率時，這個區間應該一起引用。',
                 'This is an exposure, not a correction. The true figure lies somewhere between these ends and this dataset cannot say where. Quote the net yield with this range attached.'],
    // ── the vacancy prior (v2.4) ── the level stays a guess; the shape is measured
    vacH:       ['空置率：唯一還在猜的成本，量它能量的部分',
                 'Vacancy: the last cost still being guessed, measured where it can be'],
    vacP:       ['四項成本裡，稅有文獻、管理費有雙北調查、修繕隨屋齡加權，只有空置率 %s%% 完全沒有來源——而且不分縣市、不分屋齡，每一棟收一樣的。台灣不公布租賃空置率，所以這個「水準」補不起來；但它的「形狀」補得起來。內政部的表2-3-2把低度使用（用電）住宅率做成縣市×屋齡的交叉表——是交叉表，不是兩張邊際表，所以不需要假設兩個維度獨立。',
                 'Of the four cost terms, the tax has a literature, the management fee has a two-city survey, and repairs are age-weighted. Only vacancy, at %s%%, has no source at all -- and it is charged identically to every building in every county at every age. Taiwan publishes no rental-vacancy rate, so the LEVEL cannot be sourced. The SHAPE can: 內政部\'s Table 2-3-2 gives the low-use rate for every county CROSSED WITH seven age bands -- a joint table, not two marginals, so nothing here assumes the two dimensions are independent.'],
    vacNot:     ['先講它不是什麼。低度使用住宅的分子包含二屋、待售屋、換手空檔；分母是全部房屋稅籍住宅，不是出租中的住宅。它不是房東的空置損失，本站不把它換進 headline——那會是拿一個母體的數字去代替另一個母體的數字。它能回答的是另一個問題：本站看得見的那一塊，比整體的房子更空、還是更不空。',
                 'First, what it is not. The low-use numerator counts second homes, homes for sale and homes between owners; its denominator is every dwelling on the house-tax roll, not the rented ones. It is not a landlord\'s vacancy loss, and this site does not swap it into the headline -- that would answer one population\'s question with another population\'s number. What it CAN answer is a different question: is the slice this site can see emptier than the stock, or not?'],
    vacFind:    ['答案是更空，而且差距不小。把 %s 的交叉表重新加權到本站 %s 棟配對建物自己的縣市與屋齡組合，得到 %s%%（%s%%–%s%%），而同期全國是 %s%%——高出 %spp。理由在下一張圖：屋齡五年以下的住宅，低度使用率是 %s%%，全國最高的一格，而本站配對到的建物有 %s%% 落在那一格，全國存量只有 %s%%。',
                 'The answer is emptier, and not by a little. Reweighting the %s cross-table to the actual county-and-age mix of this site\'s %s matched buildings gives %s%% (%s%%-%s%%) against %s%% nationally in the same period -- %spp higher. The next figure says why: dwellings under five years old are %s%% low-use, the highest cell in the country, and %s%% of the matched buildings sit in it against %s%% of the national stock.'],
    vacProfH:   ['低度使用率隨屋齡的形狀，與本站配對到的建物落在哪裡',
                 'How the low-use rate varies with age, and where the matched buildings sit'],
    vacProfN:   ['長條是全國各屋齡層的低度使用率（%s），刻度旁的兩個數字是本站配對建物與全國存量落在該層的比例。形狀是 U 型的：新屋與老屋都空，中間的十到二十年最不空。本站的樣本重壓在 U 型的左端，那正是報酬率最被高估的一端。',
                 'Each bar is the national low-use rate for one age band (%s); the two figures beside it are the share of this site\'s matched buildings and the share of the national stock that fall in it. The shape is a U: new and old dwellings are both empty, and the ten-to-twenty-year band is the fullest. This site\'s sample is stacked at the left end of the U, which is the end where a flat vacancy rate flatters the yield most.'],
    vacCounty:  ['只看縣市的那一條腿，方向是相反的，這正是為什麼要用交叉表。%s 全 %s 個縣市的低度使用率重新加權，本站配對集合是 %s%%，全國是 %s%%——低 %spp，因為本站看得見的建物集中在空屋較少的都會區。縣市讓它看起來比較不空，屋齡讓它明顯更空；交叉表同時處理兩者，答案是更空。',
                 'Taken on its own, the county leg points the other way -- which is exactly why the joint table matters. Reweighting the %s county rates across all %s counties puts the matched set at %s%% against %s%% nationally, %spp LOWER, because the buildings this site can see are concentrated in the metropolitan counties where fewer homes stand empty. County makes the sample look fuller; age makes it markedly emptier. The joint table holds both at once, and the answer is emptier.'],
    vacStab:    ['另一個存檔版本（%s）給的是 %s%% 對全國 %s%%，差距 %spp——水準不同，方向與量級一致。屋齡交叉表只有民國111年上、下半年存於網頁典藏，縣市層級最新到 %s；兩條腿分開公布，不相乘。還有一個讀法上的假設要講明：本站把那張表讀成「屋齡的形狀」，套用每棟在本站窗口末端的屋齡，而不是追蹤111年那一批房子後來怎麼了。',
                 'The other archived edition (%s) puts the matched set at %s%% against %s%% nationally, a gap of %spp -- a different level, the same direction and roughly the same size. Only the two 111 editions of the age cross-table are archived, while the county series runs to %s; the two legs are published separately and never multiplied together. One reading assumption is worth stating: the table is used as a profile OF AGE, applied to each building\'s age at the end of this site\'s window, not as a cohort followed forward from 111.'],
    vacCases:   ['三種收法，headline 不動', 'Three ways to charge it, headline untouched'],
    vacFlat:    ['每棟都 5%（目前）', 'A flat 5% (as charged now)'],
    vacShape:   ['5% 的水準，低度使用的形狀', 'The 5% level, low-use shape'],
    vacLevel:   ['直接收低度使用率', 'Charge the low-use rate outright'],
    vacShapeP:  ['「形狀」這一階把每棟的空置率乘上它那一格的低度使用率除以配對集合的平均，水準仍然是 %s%%，只有誰付多少變了：最低的一格收 %s%%，最高的收 %s%%。headline 的位移是 %spp——它是以配對集合正規化的，本來就該幾乎不動。會動的是橫斷面。第三張卡是界線：把低度使用率直接當空置率收，淨報酬率從 %s%% 掉到 %s%%。那是上限，不是更好的估計。',
                 'The shaped rung multiplies each building\'s vacancy by its own cell\'s rate over the matched set\'s mean. The level is still %s%%; only who pays what changes, from %s%% in the emptiest-free cell to %s%% in the emptiest. The headline shifts by %spp, which is what normalising on the matched set is supposed to do -- what moves is the cross-section. The third card is the bound: charge the low-use rate outright and the net yield goes from %s%% to %s%%. That is a ceiling, not a better estimate.'],
    vacGap:     ['對本站最重要的那個比較，三種收法的影響是：公寓對住宅大樓的淨報酬率差距 %spp（平收）→ %spp（形狀）→ %spp（直接收）。沒有一種翻轉它——這是 v2.2 型態差距的穩健性檢查，不是新發現。',
                 'On the comparison this page actually rests on: the walk-up-minus-tower net gap is %spp flat, %spp shaped and %spp at the low-use level. None of them flips it -- a robustness check on the v2.2 type gap, not a new finding.'],
    vacToggle:  ['用低度使用的形狀重算整頁', 'Recompute the whole page with the low-use shape'],
    vacToggleN: ['打開後，上面的滑桿仍然設定水準，每一棟再乘上自己那一格的係數。關掉就回到 headline 的平收。',
                 'With this on, the sliders above still set the level and each building is then scaled by its own cell\'s factor. Off is the headline\'s flat charge.'],
    vacGone:    ['為了這一節查證過、而且沒有的東西，也一起寫下來：114年的分層表在任何可達的通路都不存在。data.gov.tw 全部 52,422 筆資料集裡，「低度使用」只出現一次，而且沒有任何分層；內政統計通報只有縣市與鄉鎮市區的總比率；20坪 的面積分層只出現在民國108年的一份委託研究報告裡，那份報告自己註明分層的分母是用配對率回推的估計值，不是普查。所以這一節用的是有存檔、且是普查基礎的111年交叉表，並照實說它比本站的資料窗口早三年。',
                 'What was checked for this section and does not exist is worth writing down too: no 114 banded table is reachable on any open channel. Across all 52,422 datasets on data.gov.tw the string 低度使用 appears exactly once, with no breakdown; the 內政統計通報 series carries county and township totals only; and the 20坪 size bands appear solely inside a 108年 commissioned report which states in its own notes that the per-band denominators are grossed up from a match rate rather than counted. So this section uses the archived, census-based 111 cross-table, and says plainly that it predates the site\'s own window by three years.'],
    vacNatTick: ['全國 %s%%', 'national %s%%'],
    vacBandLab: ['%s 年', '%s yrs'],
    vacMatch:   ['本站 %s%%', 'matched %s%%'],
    vacStock:   ['存量 %s%%', 'stock %s%%'],
    lim8:       ['四項成本假設裡，空置率是唯一沒有來源的一項。它的水準補不起來（台灣不公布租賃空置率），但形狀補得起來：用內政部的縣市×屋齡交叉表重新加權，本站配對集合的低度使用率是 %s%%，同期全國 %s%%——本站看得見的建物比整體更空，因為它們新。直接把它當空置率收，淨報酬率會從 %s%% 掉到 %s%%。那是一個界線，不是一個更好的估計。',
                 'Of the four cost assumptions, vacancy is the only one with no source. Its level cannot be sourced -- Taiwan publishes no rental-vacancy rate -- but its shape can. Reweighted on 內政部\'s county-by-age cross-table, the matched set\'s low-use rate is %s%% against %s%% nationally: the buildings this site can see are EMPTIER than the stock, because they are new. Charging that rate outright would take the net yield from %s%% to %s%%, which is a bound, not a better estimate.'],
    // ── management fee: what the lease itself says (v1.9) ── two bounds, not a correction
    mgfH:       ['管理費：租約自己怎麼說', 'Management fee: what the lease itself says'],
    mgfP:       ['實價登錄租賃紀錄有一欄「備註」。在有管理員的建物裡，%s%% 的租約寫明「租金總額含管理費」，%s%% 寫明管理費由承租人另付，其餘 %s%% 沒有說（共 %s 筆市場整戶租約）。本站目前對每一棟有管理員的建物都扣一筆管理費，不管租金裡含不含。改以「棟」計：%s 棟有管理員的配對建物中，%s 棟（%s%%）至少有一筆租約寫明含管理費。',
                 'The registry\'s lease records carry a free-text 備註 (remarks) field. In buildings with on-site staff, %s%% of leases state that the rent includes the management fee, %s%% state that the tenant pays it separately, and the remaining %s%% say nothing (%s market whole-unit leases). This site currently charges the fee to every building with staff, whether or not the rent includes it. Per building: of %s matched buildings with staff, %s (%s%%) have at least one lease stating the rent includes the fee.'],
    mgfA:       ['全部有管理員的建物都扣（現行，即標題）', 'Charged to every building with staff (as now, the headline)'],
    mgfB:       ['只扣至少一筆租約寫明含管理費的建物', 'Charged only where a lease says the rent includes it'],
    mgfRule:    ['歸類規則：一棟建物只要有一筆租約寫明含管理費，就歸入「含」（以多數租約計則為 %s 棟，界線差 %s pp）。沒寫的租約視為「未註明」，不視為承租人自付——備註是自由填寫欄位，各縣市填寫習慣差很多。',
                 'Classification: a building counts as "includes" if any one of its leases says so (by majority of leases it would be %s buildings, moving the bound by %s pp). A lease that says nothing is "unstated", not "tenant pays" -- 備註 is free text and filing habits differ sharply by county.'],
    mgfNote:    ['這是兩個界線，不是修正。真實數字在兩者之間：%s%% 的租約沒有說，本站無法替它們決定誰付。標題的淨報酬率維持 %s%%，不改。',
                 'Two bounds, not a correction. The truth lies between them: %s%% of leases say nothing and this site cannot decide for them who pays. The headline net yield stays at %s%%, unchanged.'],
    mgfWb:      ['同一棟建物內，寫明含管理費的租約，每坪月租比未寫明的高 %s%%（%s 棟，四分位距 %s%% 至 %s%%，%s%% 為正），換算約每坪每月 %s 元（未寫明者中位數每坪 %s 元）；本站假設的費率是每坪每月 %s 元（臺北 %s 元）。兩個數字並列、不相除：這是描述，不是管理費的估計，資料無法分辨是費率假設偏高還是備註填寫不齊。',
                 'Inside the same building, a lease stating that the rent includes the fee rents for %s%% more per 坪 per month than one that does not (%s buildings, IQR %s%% to %s%%, %s%% positive), about NT$%s per 坪 per month on a median of NT$%s for the unflagged; the rate this site assumes is NT$%s per 坪 per month (Taipei %s). Side by side, not divided: this is descriptive, not an estimate of the fee, and the data cannot tell whether the assumed rate is high or the remarks are incomplete.'],
    mgfQT:      ['租約寫明含管理費的比例，依租約季', 'Share of leases stating the rent includes the fee, by lease quarter'],
    mgfQS:      ['有管理員建物的市場整戶租約；橫軸是租約季（Q），不是登錄季', 'Market whole-unit leases in staffed buildings; the x-axis is the lease quarter (Q), not the publication season'],
    mgfTrend:   ['從 %s 的 %s%% 到 %s 的 %s%%：填寫比例逐季上升，所以「未註明」的一群在縮小，這個界線也會隨新資料移動。',
                 'From %s at %s%% to %s at %s%%: the share stating it rises quarter by quarter, so the "unstated" group is shrinking and this bound will move with new data.'],
    mgfPartial: ['晚登錄', 'late-filed'],
    mgfCensored: ['登錄中', 'still filing'],
    mgfCountyT: ['依縣市：租約（筆）與建物（棟）分開列，不相除', 'By county: leases (筆) and buildings (棟) listed apart, never divided'],
    thLets:     ['租約數', 'Leases'],
    thIncl:     ['寫明含', 'Includes'],
    thExcl:     ['寫明另付', 'Tenant pays'],
    thBldgs:    ['有管理員建物', 'Staffed buildings'],
    thBldgsFlag: ['至少一筆含', 'Any lease includes'],
    thOther:    ['其他縣市', 'Other counties'],
    pnlMgf:     ['租約註明含管理費', 'Lease says rent includes fee'],
    pnlMgfAny:  ['至少一筆', 'At least one'],
    pnlMgfNone: ['未註明', 'None stated'],
    wfMgmtFlag: ['若只扣租約寫明含管理費的建物', 'if charged only where the lease says so'],
    // ── parking spaces (v2.0) ── the unit is a SPACE, never 坪; two assets, never subtracted
    pkEy:       ['車位', 'Parking spaces'],
    pkH:        ['同一棟樓的車位：買一個 NT$%s，租出去每月 NT$%s，毛報酬率 %s%%。',
                 'A space in the same building: buy one for NT$%s, let it for NT$%s a month, %s%% gross.'],
    pkP:        ['這一節把車位當成一個獨立的資產來算：同一棟樓裡，一個車位的成交價對上一個車位的月租金。單位是「一個車位」，不是坪 —— 登錄上的車位面積是地下室的分攤持分，不是那格車位的大小，所以本站不算車位的每坪價格。買賣一邊來自兩種紀錄（單獨賣的車位、房地+車位但車位有單獨標價），租賃一邊也是（單獨租的車位、房屋+車位但車位有單獨標租金）。每筆紀錄限定只有一個車位。',
                 'This section treats a parking space as an asset of its own: inside one building, the sale price of one space against the monthly rent of one space. The unit is one space, not 坪 -- the registry area of a space is an allocated share of the basement, not the size of the bay, so this site never computes a per-坪 parking price. The sale side comes from two record kinds (a space sold alone, or a flat+space sale that itemises the space price); so does the lease side (a space let alone, or a flat+space lease that itemises the space rent). Every record is restricted to exactly one space.'],
    pkRungStrict: ['只用單獨賣、單獨租的車位', 'Spaces sold alone and let alone only'],
    pkRungMarket: ['市價紀錄（排除社宅車位租金、排除親友間交易）—— 標題',
                 'Market records only (social-housing space rents and related-party sales out) -- the headline'],
    pkRungWide: ['加入社宅代管的車位租金', 'Social-housing space rents admitted'],
    pkPriceRent: ['車位中位價 NT$%s · 月租中位 NT$%s/月', 'median price NT$%s · median rent NT$%s/mo'],
    pkDwelling: ['對照：住宅毛報酬率 %s%%（%s 棟；本頁另有車位租金檢驗給出的界線 %s%%–%s%%）。車位和房子是兩種資產，這裡只是並列，不相減。',
                 'For context: dwelling gross yield %s%% (%s buildings; the parking-rent audit on this page bounds it at %s%%–%s%%). A space and a flat are two assets; set side by side, never subtracted.'],
    pkTypeT:    ['依車位類別（買賣與租賃兩邊同類別）', 'By space type (same type on both sides)'],
    pkTypeS:    ['實心＝市價層，空心＝加社宅層；只列該層有 %s 棟以上的類別',
                 'Filled = market rung, hollow = social-admitted rung; only types with %s or more buildings on that rung'],
    pkTypeNote: ['兩邊同類別的配對佔市價層 %s%%、加社宅層 %s%%；其餘配對（同一棟，但賣的和租的車位類別不同）不進這張圖。',
                 'Same-type pairs are %s%% of the market rung and %s%% of the social-admitted rung; the rest (same building, but the space sold and the space let are of different types) are not in this chart.'],
    pkLegMarket: ['市價層', 'market rung'],
    pkLegWide:  ['加社宅層', 'social-admitted rung'],
    pkMech:     ['【假說，本頁未量測】機械車位與坡道平面的毛報酬率差：市價層 %s（%s），加社宅層 %s（95%% CI %s–%s）。一個說得通的機制：機械車位的維修與汰換由車位所有人承擔、也比較難轉手，所以買價的折扣（機械÷平面 = %s）會大於租金的折扣（%s）。這是本頁提出的解釋，不是本頁量測到的機制；數字不論方向都照登。',
                 '[Hypothesis, not measured on this page] The gross-yield gap between mechanical and ramp-access flat spaces: market rung %s (%s), social-admitted rung %s (95%% CI %s–%s). A mechanism that would explain a positive gap: the owner bears maintenance and replacement on a mechanical space and it is harder to resell, so the price discount (mechanical ÷ flat = %s) would exceed the rent discount (%s). This is an explanation the page proposes, not a mechanism it measured; the numbers are shown whichever way they point.'],
    pkNoCiN:    ['機械車位只有 %s 棟，未達 %s 棟，不給區間', 'only %s mechanical-space buildings, under the %s needed for an interval'],
    pkCountyT:  ['依縣市（市價層，前六；每格是棟的中位數；不到 %s 棟的縣市不給區間，其他縣市合計不列報酬率）',
                 'By county (market rung, top six; each cell is a median of buildings; counties under %s buildings get no interval, and the remaining counties are counted but get no yield)'],
    pkThBldgs:  ['棟', 'Buildings'],
    pkThYield:  ['毛報酬率', 'Gross'],
    pkThPrice:  ['車位中位價 (NT$)', 'Median price (NT$)'],
    pkThRent:   ['月租中位 (NT$/月)', 'Median rent (NT$/mo)'],
    pkValidH:   ['這些紀錄為什麼可以混用：同棟內的三個檢驗', 'Why the record kinds can be pooled: three within-building checks'],
    pkValidP:   ['每個檢驗都是同一棟樓裡兩種紀錄的中位數之比（n = 兩種紀錄都有的棟數）。比值接近 1 才允許混用；四分位距照登，因為房地+車位裡的車位標價是買賣雙方自己的分配，「灌車位」是已知作法。',
                 'Each check is the ratio of the two record kinds\' medians inside the same building (n = buildings carrying both). A ratio near 1 is what licenses pooling; the interquartile range is shown because the itemised space price in a flat+space sale is the parties\' own allocation, and loading price into the space is a known practice.'],
    pkV1:       ['房地+車位的車位標價 ÷ 單獨賣的車位價', 'Itemised space price in a flat+space sale ÷ a space sold alone'],
    pkV2:       ['社宅代管的車位租金 ÷ 市價車位租金', 'Social-housing space rent ÷ market space rent'],
    pkV3:       ['房屋+車位的車位標租 ÷ 單獨租的車位租金', 'Itemised space rent in a flat+space lease ÷ a space let alone'],
    pkThN:      ['棟數 n', 'Buildings n'],
    thRatio:    ['中位比值', 'Median ratio'],
    thIqr:      ['四分位距', 'IQR'],
    pkThin:     ['（太薄）', '(thin)'],
    pkV3Thin:   ['第三個檢驗只有 %s 棟，不足以單獨支持任何結論。所以另外算：市價層若只用單獨租的車位是 %s%%（%s 棟），只用單獨賣的車位是 %s%%（%s 棟）；%s。',
                 'The third check rests on %s buildings, too thin to carry a conclusion on its own. So it is computed the other way too: the market rung on spaces let alone only is %s%% (%s buildings), on spaces sold alone only %s%% (%s buildings); %s.'],
    pkInside:   ['兩者都落在標題層的信賴區間內', 'both inside the headline rung\'s interval'],
    pkOutside:  ['至少一個落在標題層的信賴區間外', 'at least one outside the headline rung\'s interval'],
    pkWideRule: ['加社宅層的門檻：同棟內社宅車位租金 ÷ 市價車位租金的中位比值與 1 相差不超過 %s，且至少 %s 棟。本次 %s（%s 棟）→ %s。背後的假說（本頁未量測）：包租代管的租金補貼落在住宅租金，不落在車位租金。',
                 'The social-admitted rung is shown only if the within-building median ratio of social to market space rent is within %s of 1 on at least %s buildings. This build: %s (%s buildings) → %s. The hypothesis behind admitting it (not measured here): the 包租代管 subsidy applies to the dwelling rent, not the space.'],
    pkLicensed: ['列出', 'shown'],
    pkNotLicensed: ['不列', 'withheld'],
    pkSocialNote: ['加社宅層的配對有 %s%% 用的是社會住宅包租代管的車位租金，%s%% 的棟在%s：這是「誰會填寫車位租金欄位」造成的選樣，不是市場。兩層都登，標題用市價層。',
                 '%s%% of the social-admitted rung\'s pairs use a social-housing 包租代管 space rent and %s%% of its buildings are in %s: that is selection on who fills in the space-rent field, not the market. Both rungs are published and the headline is the market rung.'],
    pkBand:     ['配對的毛報酬率落在 %s%%–%s%% 之外者視為登錄錯誤（例如月租登錄為 NT$100）而剔除：市價層 %s 筆、加社宅層 %s 筆。這是和住宅相同的區間，不是為車位另設的門檻。',
                 'Pairs with a gross outside %s%%–%s%% are treated as filing errors (a monthly rent entered as NT$100, say) and dropped: %s on the market rung, %s on the social-admitted rung. It is the same band the dwellings use, not a threshold set for spaces.'],
    pkTimeNote: ['和住宅一樣，配對允許買賣與租賃相差 ±%s 季，所以這是三年窗口的平均，不是某一季的即期報酬率。把窗口放寬到不限季數，市價層會從 %s 棟變成 %s 棟，中位數 %s%%。',
                 'As for dwellings, a sale and a lease may be up to %s quarters apart, so this is a window average, not a spot yield for one quarter. With no window at all the market rung goes from %s to %s buildings, median %s%%.'],
    pkWfT:      ['紀錄從哪裡來（只計單一車位的交易）', 'Where the records come from (single-space transactions only)'],
    pkWfSaleStand: ['單獨賣的車位', 'Spaces sold alone'],
    pkWfSaleBund: ['房地+車位，車位有標價', 'Flat+space sales with an itemised space price'],
    pkWfLeaseStand: ['單獨租的車位', 'Spaces let alone'],
    pkWfLeaseBund: ['房屋+車位，車位有標租', 'Flat+space leases with an itemised space rent'],
    pkWfSocial: ['其中社會住宅', 'of which social housing'],
    // ── un-itemised parking rent: the audit (v2.0) ── two bounds, headline untouched
    pkaH:       ['未列明的車位租金：檢驗一個前提', 'Un-itemised parking rent: testing an assumption'],
    pkaP:       ['本站在 v2.0 以前把含車位的租約留下、只扣掉車位面積，前提是「車位總額元為零，多半代表車位沒有另外計租」。這個前提可以在同一棟建物內檢驗：拿「租賃房屋+車位」且車位租金有列明的租約，和同棟沒列明的相比，比的是扣除前的總租金（房子加車位）除以總面積。若前提成立，沒列明那筆每平方公尺應該比有列明的低約 %s%%（有列明者的車位租金占總租金的中位數）；若車位租金其實在房租裡，兩者應該一樣。結果：%s 棟同時有兩種租約，比值中位數 %s（95%% 信賴區間 %s–%s，四分位距 %s–%s）。',
                 'Until v2.0 this site kept a lease that bundles a parking space and subtracted only the space\'s area, on the assumption that a zero 車位總額元 usually means the space came at no extra rent. The assumption can be tested inside one building: leases marked 租賃房屋+車位 with the parking rent itemised, against leases in the same building where it is not, comparing TOTAL rent (dwelling plus space) per square metre of total area, before any subtraction. If the assumption held, the un-itemised lease should sit about %s%% lower (the median parking share of total rent where it is itemised); if the parking rent is inside the dwelling rent, the two should be equal. Result: %s buildings carry both kinds; the median ratio is %s (95%% CI %s–%s, IQR %s–%s).'],
    pkaVerdictFails: ['判定：前提不成立。整個信賴區間（%s–%s）落在「一樣」附近，高於「低 %s%%」的區域（%s–%s）。判定規則寫在下面，所有常數都在資料檔裡，測試會用它們重算一次判定。',
                 'Verdict: the assumption fails. The whole interval (%s–%s) sits at "equal", above the "%s%% lower" band (%s–%s). The rule is stated below; every constant is in the data file, and a test re-derives the verdict from them.'],
    pkaVerdictHolds: ['判定：前提成立。信賴區間（%s–%s）落在「低 %s%%」的區域（%s–%s）內，且不碰到「一樣」。判定規則寫在下面，所有常數都在資料檔裡，測試會用它們重算一次判定。',
                 'Verdict: the assumption holds. The interval (%s–%s) sits inside the "%s%% lower" band (%s–%s) and clear of "equal". The rule is stated below; every constant is in the data file, and a test re-derives the verdict from them.'],
    pkaVerdictInc: ['判定：無法判定。信賴區間（%s–%s）既不完全落在「一樣」之上，也不落在「低 %s%%」的區域（%s–%s）內。判定規則寫在下面，所有常數都在資料檔裡，測試會用它們重算一次判定。',
                 'Verdict: inconclusive. The interval (%s–%s) neither sits wholly above the "%s%% lower" band (%s–%s) nor inside it. The rule is stated below; every constant is in the data file, and a test re-derives the verdict from them.'],
    pkaRule:    ['判定規則：以同棟「總租金／總面積」比值的 95%% 信賴區間為準，至少 %s 棟。成立區 = 1 減去有列明者的車位租金占比，正負 %s（本次 %s–%s）。區間下限高於成立區上緣 → 不成立；區間碰到成立區、且上限低於 1 減 %s → 成立；其他情形 → 無法判定。規則不是在看資料之前定的：偵察階段已經看過同一批 191 棟的初步結果，所以本頁不稱它「預先登錄」。',
                 'Rule: the 95%% CI of the within-building total-rent-per-m2 ratio, on at least %s buildings. Holds-band = 1 minus the itemised parking share, plus or minus %s (this build %s–%s). CI lower end above the band → fails; CI overlaps the band and its upper end is below 1 minus %s → holds; anything else → inconclusive. The rule was not fixed before the data were seen -- the scouting pass had already seen a first result on the same buildings -- so this page does not call it pre-registered.'],
    pkaTblCap:  ['同棟內的比較。比值 = 前者／後者的各棟中位數，再取棟的中位數；最後兩欄是兩種前提各自預期的數字，並列不相除。',
                 'Within-building comparisons. Ratio = per-building median of the first over the second, then the median across buildings; the last two columns are what each hypothesis predicts, set side by side.'],
    pkaRow1:    ['總租金／總面積：未列明 vs 有列明', 'Total rent per m2: un-itemised vs itemised'],
    pkaRow1a:   ['同上，只計車位面積有列明者', 'Same, un-itemised rows with an itemised area only'],
    pkaRow1b:   ['同上，只計車位完全未列明者', 'Same, un-itemised rows with nothing itemised'],
    pkaRow2:    ['扣車位後每坪房租：未列明 vs 有列明', 'Dwelling rent per 坪 after subtraction: un-itemised vs itemised'],
    pkaRow3:    ['扣車位後每坪房租：未列明 vs 不含車位', 'Dwelling rent per 坪 after subtraction: un-itemised vs no parking'],
    pkaRow4:    ['扣車位後每坪房租：有列明 vs 不含車位（對照）', 'Dwelling rent per 坪 after subtraction: itemised vs no parking (control)'],
    thIfHolds:  ['若前提成立', 'If it held'],
    thIfFails:  ['若車位租金在房租裡', 'If the rent is inside'],
    pkaCorr:    ['另外三個比較的讀法。扣掉車位面積之後，未列明者的每坪房租比同棟有列明者%s（%s 棟，區間 %s%% 至 %s%%；若車位租金在房租裡，預期約 +%s%%）。未列明者比同棟不含車位的租約%s（%s 棟，區間 %s%% 至 %s%%）。對照組：有列明、扣掉車位租金之後的租約，比不含車位的%s（%s 棟，區間 %s%% 至 %s%%）。這些結果與「車位租金在房租裡」一致；它們否定的是「車位免費」這個前提。',
                 'How to read the other three. After the space\'s area is taken out, an un-itemised lease rents %s per 坪 than an itemised one in the same building (%s buildings, %s%% to %s%%; about +%s%% is what "the parking rent is inside" predicts). It rents %s than a no-parking lease in the same building (%s buildings, %s%% to %s%%). Control: an itemised lease, with its parking rent subtracted, rents %s than a no-parking one (%s buildings, %s%% to %s%%). These results are consistent with the parking rent sitting inside the dwelling rent; what they reject is the free-space assumption.'],
    pkaMore:    ['高 %s%%', '%s%% more'],
    pkaLess:    ['低 %s%%', '%s%% less'],
    pkaWho:     ['有列明的 %s 筆租約是誰填的：%s。未列明的一方多為房東自填；這個比較在同棟內仍受填寫者類型的干擾，照登。',
                 'Who itemised the %s priced leases: %s. The un-itemised side is mostly landlord-filed; the comparison is landlord-type confounded even within building, and is published as such.'],
    pkaSocial:  ['被本頁排除的社會住宅租約另做同一個檢驗（只是佐證，不進判定）：%s 棟，比值 %s（%s–%s）——同樣不在「低 %s%%」附近。',
                 'The same test on the social-housing leases this page excludes (corroboration only, never in the verdict): %s buildings, ratio %s (%s–%s) -- likewise nowhere near "%s%% lower".'],
    pkaBoundsH: ['三種處理：標題與兩個界線', 'Three treatments: the headline and two bounds'],
    pkaA:       ['舊作法（v1.0–v2.0 的標題）：保留、只扣面積', 'The old treatment (the headline from v1.0 to v2.0): keep, subtract area only'],
    pkaB:       ['整筆排除未列明的租約', 'Drop the un-itemised leases'],
    pkaC:       ['推算車位租金並扣除（v2.1 起的標題）', 'Impute a space rent and subtract it (the headline from v2.1)'],
    pkaNet:     ['淨 %s%%', 'net %s%%'],
    pkaImpRule: ['推算規則（以車位計）：同棟有列明的車位租金中位數（%s 筆），否則該縣市中位數（至少 %s 筆有列明；%s 筆），否則全國中位數 NT$%s/月（%s 筆）。推算中位數 NT$%s/月；扣除後低於 NT$3,000 門檻的 %s 筆剔除。',
                 'Imputation rule (per space): the same building\'s itemised median (%s rows), else the county median where it has at least %s itemised rows (%s rows), else the national median NT$%s/mo (%s rows). Imputed median NT$%s/mo; %s rows fell under the NT$3,000 floor after subtraction and were dropped.'],
    pkaExpo:    ['牽涉範圍：有 %s 筆租約（清理後 %s 筆的 %s%%）是含車位但未列明租金的，佔所有含車位租約的 %s%%。標題的 %s 對配對中有 %s 對（%s%%）靠這些租約；%s 棟配對建物中 %s 棟（%s%%）至少有一對，%s 棟（%s%%）全部靠它們。',
                 'What rests on it: %s of the %s cleaned leases (%s%%) bundle a space with no itemised rent, %s%% of all bundled leases. Of the headline\'s %s pairs, %s (%s%%) rest on them; of %s matched buildings, %s (%s%%) carry at least one and %s (%s%%) rest on nothing else.'],
    pkaThPairs: ['配對', 'Pairs'],
    pkaThUnp:   ['其中未列明車位', 'On un-itemised'],
    pkaCovT:    ['配對建物數：三種處理', 'Matched buildings under the three treatments'],
    pkaCovS:    ['整筆排除少掉 %s 棟；推算扣除（標題）和舊作法一樣保留全部 %s 棟。階梯上「整筆排除含車位」那一階是 %s 棟。',
                 'Dropping loses %s buildings; imputing (the headline) keeps all %s, as the old treatment did. The ladder rung that drops every bundled transaction is %s buildings.'],
    pkaCovOld:  ['舊作法：整筆排除含車位', 'Old rung: drop all bundled'],
    pkaCovDrop: ['整筆排除未列明', 'Drop un-itemised'],
    pkaCovNow:  ['推算扣除（標題）＝舊作法', 'Impute (headline) = old treatment'],
    pkaTrade:   ['為什麼選推算而不是整筆排除。整筆排除會少掉 %s 棟（%s%%），而且不是隨機的一批：只靠未列明租約的建物，毛報酬率中位數 %s%% 對其餘 %s%%，屋齡中位數民國 %s 年完工對 %s 年，%s%% 是住宅大樓對 %s%%——比較新、比較多大樓。排除它們會把數字往上推。推算扣除保留全部 %s 棟：毛報酬率由舊作法的 %s%% 變成 %s%%（%s pp），淨報酬率由 %s%% 變成 %s%%。這是 v2.1 起的標題。',
                 'Why impute rather than drop. Dropping loses %s buildings (%s%%), and not a random batch: buildings resting only on un-itemised leases have a median gross of %s%% against %s%% for the rest, a median completion year of ROC %s against %s, and %s%% are towers against %s%% -- newer, and more towers. Dropping them pushes the number up. Imputing keeps all %s buildings: gross goes from the old %s%% to %s%% (%s pp) and net from %s%% to %s%%. That is the headline from v2.1.'],
    pkaNote:    ['標題自 v2.1 起採推算扣除：%s%%／%s%%。舊作法的 %s%%／%s%% 保留在這裡當界線，不刪——修正是累積的，不是取代。',
                 'From v2.1 the headline imputes and subtracts: %s%% / %s%%. The old treatment\'s %s%% / %s%% stays here as a bound, not deleted -- corrections accrete, they do not replace.'],
    wfParkOld:  ['若不扣推算的車位租金（v2.0 以前的作法）', 'if no imputed space rent were subtracted (the treatment before v2.1)'],
    pnlRentOld: ['舊作法月租中位（未扣推算車位租金）', 'Median rent under the old treatment (no imputed space rent)'],
    lim5:       ['%s%% 的租約含車位但未列明車位租金。本站曾假設那些車位免費，同棟檢驗否定了這個前提，所以標題自 v2.1 起推算並扣除車位租金：%s%%（舊作法 %s%%；整筆排除 %s%%，少 %s 棟）。推算是估計，不是登錄數字。',
                 '%s%% of leases bundle a space with no itemised rent. This site used to assume those spaces were free; a within-building test rejected that, so from v2.1 the headline imputes and subtracts a space rent: %s%% (old treatment %s%%; dropping them %s%% on %s fewer buildings). The imputation is an estimate, not a registered figure.'],
    // ── the walk-up hypothesis, settled (v2.2) ── two questions, two verdicts
    wuEy:       ['已結案的假說', 'A hypothesis, settled'],
    wuH:        ['配對到的公寓比配對到的住宅大樓高 %spp — 但本登錄答不出這是不是母體事實',
                 'Matched walk-ups out-yield matched towers by %spp — and this registry cannot say whether that is true of the population'],
    wuP1:       ['本站的原始假說是：扣掉管理費之後，公寓的收益率會高於住宅大樓。這句話裡其實有兩個問題——誰比較高，以及為什麼。兩個問題本節都給了答案，而兩個答案都不是原本預期的那種。',
                 'This site set out to test one prediction: that walk-ups out-yield towers once management fees are netted off. That sentence holds two questions -- which yields more, and why. This section answers both, and neither answer is the kind that was expected.'],
    wuVLevel:   ['層級一：誰比較高', 'Question one: which yields more'],
    wuVMech:    ['層級二：為什麼', 'Question two: why'],
    wuVResolved: ['配對樣本內差距穩定為正', 'the gap is positive and stable inside the matched sample'],
    wuVUnansSel: ['無法回答：兩邊的樣本各自偏斜', 'unanswerable: each sample is separately skewed'],
    wuVUnansPre: ['無法回答：精度不足', 'unanswerable: not enough precision'],
    wuVInc:     ['無法判定', 'inconclusive'],
    wuVMechKill: ['假說指名的機制已被推翻', 'the mechanism the hypothesis named is falsified'],
    wuVMechUnans: ['成因無法歸因：型態與屋齡分不開', 'the cause cannot be attributed: type and age cannot be separated'],
    wuCov:      ['能算的公寓有 %s 棟，佔全站 %s 棟的 %s%%。有成交紀錄的公寓共 %s 棟，配對率 %s%%——這是全站三種型態裡最低的。公寓成交紀錄 %s 筆，配對數 %s 對，中位每棟 %s 對（住宅大樓 %s 對）。全國 4~5 層住宅存量 %s 宅（房屋稅籍 %s）與本站的棟數並列，不相除：一個是宅，一個是棟。',
                 'The site can price %s walk-up buildings out of its %s, or %s%%. Walk-ups with a sale on file: %s buildings, a %s%% match rate -- the lowest of the three types. Walk-up sale records: %s; pairs: %s, a median of %s per building against %s for towers. The national 4-to-5-storey stock, %s dwellings (house-tax roll %s), sits beside the site\'s building count and is never divided into it: one counts 宅, the other 棟.'],
    wuRepH:     ['兩邊的樣本各自偏斜', 'Each sample is separately skewed'],
    wuRep:      ['配對到的公寓和有成交但配不到的公寓，幾乎是同一批：屋齡中位數民國 %s 年對 %s 年完工，%s 坪對 %s 坪（差 %s%%），每坪 %s 元對 %s 元。住宅大樓那一邊不是：配對到的中位 %s 坪，配不到的 %s 坪，差 %s%%。兩個樣本各自以不同的方式偏離自己的母體，所以它們的差距不能當成母體的差距。',
                 'The matched walk-ups look like the walk-ups that sold and did not match: completed ROC %s against %s, %s against %s ping (a %s%% difference), NT$%s against NT$%s per ping. The tower side does not: matched towers run %s ping against %s for the unmatched, a %s%% difference. Each sample departs from its own population in a different way, so the difference between them is not a difference between the populations.'],
    wuPrec:     ['精度不是限制。差距 %spp；在這個樣本數下，本站自己的兩段式拔靴法能偵測到 %spp，觀測值是它的 %s 倍（95%% 區間 %s 到 %s）。問題不在雜訊。',
                 'Precision is not the binding constraint. The gap is %spp; at this sample size the site\'s own two-stage bootstrap can detect %spp, and the observed value is %s times that (95%% interval %s to %s). Noise is not the problem.'],
    wuCtl:      ['方向很穩。每一個涵蓋過半配對公寓的控制族，中位差距都是正的：價格十分位 %spp、行政區 %spp、縣市 %spp、屋齡區間 %spp、坪數區間 %spp、有無管理員 %spp。同時控制行政區與屋齡區間、每格至少 %s 棟，可用的格子是 %s 個。',
                 'The sign is stable. Every control family covering more than half the matched walk-ups gives a positive median gap: price decile %spp, district %spp, county %spp, age band %spp, size band %spp, manager or none %spp. Holding district and age band jointly at %s buildings a cell leaves %s usable cells.'],
    wuFCtlT:    ['每個控制之下的差距', 'The gap under each control'],
    wuFCtlS:    ['公寓中位數減住宅大樓中位數，單位 pp，取各格差距的中位數。淡色列涵蓋不到一半的配對公寓，不進入判決；行政區乘屋齡區間沒有任何一格達標。',
                 'Walk-up median minus tower median in percentage points, taken as the median across cells. Faded rows cover less than half the matched walk-ups and do not enter the verdict; district by age band produces no qualifying cell at all.'],
    wuSupp:     ['沒有共同支撐，這是成因問題的死路。公寓屋齡中位數 %s 年（%s 到 %s），住宅大樓 %s 年（%s 到 %s）；四十年以上的大樓只有 %s%%，二十年以下的公寓只有 %s%%。在兩者重疊的 %s 到 %s 年窗口裡，差距仍是 %spp（%s 到 %s，%s 棟對 %s 棟）——方向一致，但樣本已經小到只能當佐證。',
                 'There is no common support, and that is where the question of cause dies. Walk-ups have a median age of %s years (%s to %s), towers %s (%s to %s); only %s%% of towers are over forty and only %s%% of walk-ups under twenty. Inside the %s-to-%s-year window where they overlap the gap is still %spp (%s to %s, on %s against %s buildings) -- the same direction, but on a sample small enough to be corroboration only.'],
    wuFAgeT:    ['屋齡分布：公寓與住宅大樓', 'Age distribution: walk-ups and towers'],
    wuFAgeS:    ['每一條是該屋齡的棟數佔該型態的比例。兩條幾乎不重疊，這就是「是公寓」與「已經四十五歲」分不開的原因。',
                 'Each bar is that age\'s share of its own type\'s matched buildings. The two barely overlap, and that is why being a walk-up cannot be separated from being forty-five years old.'],
    wuMech:     ['假說指名的機制已經死了。有管理員的比例，公寓 %s%%、住宅大樓 %s%%——管理費這個變數幾乎就是建物型態本身。但在兩邊都沒有管理員、模型收費為零的建物裡（%s 棟對 %s 棟），差距仍是 %spp（%s 到 %s）。差距不需要管理費就存在，所以原本的解釋是錯的。',
                 'The mechanism the hypothesis named is dead. A manager is recorded for %s%% of walk-ups and %s%% of towers -- the fee variable is very nearly the building type itself. Yet among buildings with no manager on either side, where the modelled fee is zero (%s against %s buildings), the gap is still %spp (%s to %s). The gap exists without the fee, so the original explanation is wrong.'],
    wuThMgr:    ['管理員', 'Manager'],
    wuThNW:     ['公寓（棟）', 'Walk-ups'],
    wuThNT:     ['住宅大樓（棟）', 'Towers'],
    wuThGap:    ['毛差距', 'Gross gap'],
    wuThNet:    ['淨差距', 'Net gap'],
    wuYes:      ['有', 'yes'],
    wuNo:       ['無', 'none'],
    wuUnans:    ['所以本站把這個假說結案為「本登錄無法回答」，而不是留著不管。差距在配對樣本裡是真的，方向在每一個控制下都一致，機制則已被推翻；但配對到的公寓和配對到的住宅大樓，各自以不同的方式偏離自己的母體（前者差 %s%%，後者差 %s%%），所以這個差距不能當成「公寓比大樓好」的母體陳述。把它寫成無法回答，比留著一個看起來已經回答的問題誠實。',
                 'So the site closes this hypothesis as one this registry cannot answer, rather than leaving it open. The gap inside the matched sample is real, its sign holds under every control, and the mechanism is falsified; but the matched walk-ups and the matched towers each depart from their own population in a different way (%s%% against %s%%), so the gap cannot be read as a population statement that walk-ups beat towers. Publishing it as unanswerable is more honest than leaving a question that looks answered.'],
    wuNeed:     ['能回答的資料有兩筆，都拿不到。一是完整的租約母體：本登錄的租賃案件只來自租賃住宅服務業與不動產經紀業，屋主自租的公寓從不進檔——這是配對率 %s%% 的直接原因。二是房屋稅籍的建號級微資料（型態、屋齡、樓層），僅供機關調用；已公布的都是縣市別「宅」數彙總，補得了分母，補不了配對。',
                 'Two datasets would answer it and neither is available. A complete population of leases: this registry only receives leases filed by licensed rental-service and brokerage firms, so a walk-up let directly by its owner never enters -- which is the direct cause of the %s%% match rate. And building-level house-tax micro-data (type, age, floor), released to institutions only; what is published is county aggregates in 宅, which sharpen a denominator without closing the gap.'],
    wuRule:     ['規則與常數（不是預先註冊的——寫定時已經看過原始差距，和車位租金那一節同樣的揭露）：配對公寓少於 %s 棟為無法判定；差距小於兩段式拔靴標準誤的 %s 倍為精度不足；配對與未配對的屋齡、坪數、每坪價中位數任一相差超過 %s%%，或加權回母體後變號，為樣本偏斜無法回答；每個涵蓋過半樣本的控制族同號比例需達 %s%%；成因要能歸因，需要行政區乘屋齡區間至少 %s 格、每格 %s 棟。本次結果：最大偏斜 %s%%，可用格子 %s 個。',
                 'The rule and its constants (not pre-registered -- the raw gap was known when it was written, the same disclosure the parking-rent section carries): fewer than %s matched walk-up buildings is inconclusive; a gap under %s bootstrap standard errors is unanswerable on precision; a matched-versus-unmatched median differing by more than %s%% on age, size or price per ping, or a sign flip after reweighting, is unanswerable on selection; every control family covering more than half the sample must agree in sign %s%% of the time; and attributing the cause needs at least %s district-by-age cells of %s buildings each. This build: largest skew %s%%, usable cells %s.'],
    wuAccrete:  ['先前的版本把這個假說列為「仍然成立、尚未解決」，毛差距 %spp、淨差距 %spp。那一列留著（見上一節），這一節是它的結案。',
                 'Earlier versions listed this hypothesis as alive and unresolved, at %spp gross and %spp net. That rung stays (see the section above); this section is its closing.'],
    lim6:       ['本站的原始假說（公寓比住宅大樓好）已結案為「本登錄無法回答」：差距在配對樣本裡穩定為 %spp，但配對到的公寓與住宅大樓各自偏離母體，且機制已被推翻。詳見進階模式。',
                 'This site\'s founding hypothesis -- that walk-ups beat towers -- is closed as one this registry cannot answer: the gap is a stable %spp inside the matched sample, but the matched walk-ups and towers each depart from their own population, and the mechanism is falsified. Advanced mode has the proof.'],
    // ── what 6% identifies (v2.3) ── bounds, never a point; no rung says "Taiwan"
    pidEy:      ['看不見的那 94%', 'The 94% that cannot be seen'],
    pidH:       ['本站看得到 %s%%。那 %s%% 容許的說法，是一個區間，不是一個數字。',
                 'This site sees %s%%. What the other %s%% permits is an interval, not a number.'],
    pidLede:    ['前面每一個數字，都是這 %s 棟建物的中位數。有成交紀錄的建物有 %s 棟，其餘 %s 棟本站配不到租約。把它們當成不存在，等於假設它們和看得到的一樣——這一節不做那個假設，改成問：看得到 %s%%，到底容許說什麼？答案是一串區間，每往下一階就多一個「你可以不同意」的假設。',
                 'Every number before this one is a median of %s buildings. %s buildings have a sale on record; for the other %s this site cannot find a lease. Treating them as absent is the same as assuming they look like the ones it can see. This section refuses that assumption and asks instead: seeing %s%%, what may anyone actually claim? The answer is a series of intervals, each rung adding one assumption you are free to reject.'],
    pidWhy:     ['中位數的最壞情況區間，只有在看得到的部分超過一半之後才會離開支撐區。本站看得到 %s%%；把本站自己的五道篩選全部拿掉，實價登錄的結構上限是 %s%%——不到一半。所以第一階不是「清理得不夠好」，是清理再好也不會動。這是結論，不是免責聲明。',
                 'A median\'s worst-case interval only leaves the support band once more than half the population is observed. This site sees %s%%; with all five of its own filters removed the registry\'s structural ceiling is %s%% -- less than half. So the first rung is not a sign of poor cleaning: no cleaning moves it. That is the result, not a disclaimer.'],
    pidScope:   ['範圍：窗口內有成交紀錄的建物，%s 棟，以「棟」計——本站自己的母體、自己的單位。全國 1~3 層透天佔住宅存量 42.7%%，本站的篩選在定義上就排除它們，沒有任何觀測值落在那裡，所以沒有任何一階說得到「全臺灣」。本節也不把房屋稅籍的「宅」分布換算成「棟」權重：一棟大樓的宅數是一棟公寓的好幾十倍，那個換算就是當年「1,086 棟裡有一棟」被撤回的同一個錯誤，而且實測只值 0.007pp。',
                 'Scope: the %s buildings with a recorded sale in the window, counted in 棟 -- this site\'s own population and its own unit. Nationally, 1-to-3-storey 透天 are 42.7%% of the dwelling stock and this site\'s filters exclude them by construction, so no observation falls there and no rung here speaks about Taiwan. Nor does this section convert house-tax 宅 shares into 棟 weights: a tower holds dozens of dwellings and a walk-up a handful, and that conversion is the same error that got "one building in 1,086" withdrawn -- measured, it is worth 0.007pp.'],
    pidFigT:    ['每多一個假設，區間短多少', 'What each assumption buys'],
    pidFigS:    ['每一條是毛報酬率中位數的區間，軸是本站的品質區間 %s%%–%s%%。條內的刻度是 %s%%，也就是配對到的 %s 棟的中位數——它是區間裡的一個點，不是答案。區間中點沒有任何意義，本頁刻意不畫。',
                 'Each bar is an interval for the median gross yield, on an axis running the site\'s own quality band, %s%% to %s%%. The tick inside each bar is %s%%, the median of the %s matched buildings -- a point inside the interval, not the answer. The midpoint of an interval means nothing and is deliberately not drawn.'],
    pidR_band:  ['只用本站自己的品質區間', 'The site\'s own cleaning band, and nothing else'],
    pidR_type_support: ['配不到的，落在同型態已配對建物的最小到最大值之間', 'Unmatched lie between the lowest and highest seen for their own type'],
    pidR_type_trim: ['…落在同型態的第 5 到第 95 百分位（近似假設）', '...inside their own type\'s 5th-95th percentile (a resemblance assumption)'],
    pidR_type_price: ['…同型態、且同一個每坪價十分位', '...within their own type AND their own price-per-ping decile'],
    pidR_type_price_age: ['…再加同一個屋齡區間（反而變寬）', '...plus their own age band (which makes it WIDER)'],
    pidR_mts_up:   ['若配不到的更高（價格梯度，未量測）', 'if the unmatched yield MORE (price gradient, unmeasured)'],
    pidR_mts_down: ['若配不到的更低（流動性選擇，未量測）', 'if the unmatched yield LESS (liquidity selection, unmeasured)'],
    pidBuys:    ['短 %spp', '%spp shorter'],
    pidWider:   ['反而長 %spp', '%spp LONGER'],
    pidTrimWarn: ['第三階買走了 %spp，是整張表上最大的一筆——但它買的方式值得看清楚。「落在第 5 到第 95 百分位」比「和已配對的分布一樣」更強：它不准任何一棟配不到的建物，落在自己型態的前 5%%。所以它不是支撐假設，是近似假設，上一階（不修剪）留在圖上就是為了讓這筆帳看得見。',
                 'The third rung buys %spp, the largest single step on the ladder -- but how it buys is worth seeing. "Inside the 5th-95th percentile" is stronger than "distributed like the matched ones": it forbids any unmatched building from sitting in its own type\'s top 5%%. It is a resemblance assumption, not a support one, and the untrimmed rung stays on the chart so the bill is visible.'],
    pidAgeWarn: ['多控制一個變數，不一定多知道一點。加上屋齡區間之後格子變細，%s 個格子（共 %s 個）的已配對建物不足 %s 棟，%s 棟建物的質量因此退回到比較弱的型態層假設——區間反而長了 %spp。這一階公布出來，就是因為它失敗。',
                 'Conditioning on one more variable does not always identify more. Adding the age band thins the cells: %s of %s hold fewer than %s matched buildings, so the mass of %s buildings falls back to the weaker type-level assumption and the interval gets %spp LONGER. This rung is published because it fails.'],
    pidMts:     ['殘餘選擇的方向，本頁不選邊。兩個說法都成立、都沒有量測：已配對的建物每坪貴 %s%%，而報酬率在十個價格十分位上單調遞減——這指向配不到的更高（%s%% 到 %s%%）。但「同時賣掉又在四季內出租」挑的是流動性好的投資型物件，這指向配不到的更低（%s%% 到 %s%%）。第一個理由不能當假設用，因為價格十分位在上一階已經控制過了。所以兩邊都登，不簽名。',
                 'The direction of the residual selection, and this page does not pick one. Both arguments hold and neither is measured: matched buildings are %s%% dearer per ping and the yield falls monotonically across all ten price deciles, which points to the unmatched yielding MORE (%s%% to %s%%). But matching requires both selling and letting within four quarters, which selects liquid investor stock, and that points to the unmatched yielding LESS (%s%% to %s%%). The first argument cannot be used as an assumption at all, because price decile is already conditioned on in the rung above. So both are published and neither is signed.'],
    pidComp:    ['配不到的建物不是隨機的一批。住宅大樓佔有成交紀錄建物的 %s%%、佔配對到的 %s%%（配對率 %s%%）；公寓佔 %s%% 對 %s%%（配對率 %s%%）。上面的每一階都在每個型態內部分開處理，就是因為這個落差。',
                 'The buildings it cannot see are not a random batch. Towers are %s%% of the buildings with a sale and %s%% of the matched ones (a %s%% match rate); walk-ups %s%% against %s%% (a %s%% match rate). Every rung above conditions within type precisely because of that gap.'],
    pidUnans:   ['把同一個方法用在單一型態上，就看得出它的極限：%s的配對率是 %s%%，它自己的區間是 %s%% 到 %s%%，寬 %spp——足以把本站另一節量到的 %spp 型態差距整個吞掉。部分識別救不了那個假說，它只是把「離得救有多遠」標出來。',
                 'Turn the same method on a single type and its limit shows: %s match at %s%%, their own interval runs %s%% to %s%%, a width of %spp -- wide enough to swallow whole the %spp type gap measured elsewhere on this page. Partial identification does not rescue that hypothesis; it prices exactly how far from rescue it is.'],
    pidMid:     ['請不要引用區間的中點。區間的意思是「端點之間每一個值都還沒有被排除」，中點沒有比別的點更可能。要一個數字的話，本站有的是配對到的 %s 棟的中位數 %s%%，而它是一個被選出來的十六分之一的中位數——這一節整節都在說它為什麼不能當全體。',
                 'Please do not quote the midpoint. An interval says every value between its ends is still not ruled out; the middle is no likelier than the edges. If a single number is wanted, this site has one -- the median of its %s matched buildings, %s%% -- and it is the median of a selected sixteenth, which is what this entire section exists to explain.'],
    pidCI:      ['端點本身也有抽樣誤差（下端 %s–%s，上端 %s–%s，%s 次拔靴）。那是「端點量得準不準」，不是「報酬率落在哪裡」——別把它讀成區間的區間。',
                 'The endpoints carry sampling error of their own (lower %s-%s, upper %s-%s, %s bootstrap draws). That is how precisely the endpoints are measured, not where the yield lies -- do not read it as an interval around the interval.'],
    lim7:       ['本站看得到有成交紀錄建物的 %s%%。在已寫明的假設下，這個母體的毛報酬率中位數落在 %s%% 到 %s%% 之間；完全不加假設則是本站的品質區間 %s%%–%s%%。標題的 %s%% 是配對樣本的中位數，落在區間內，但它不是母體的估計值。',
                 'This site sees %s%% of the buildings with a sale on record. Under the assumptions it states, that population\'s median gross yield lies between %s%% and %s%%; with no assumptions at all it is the site\'s own quality band, %s%% to %s%%. The headline %s%% is the median of the matched sample -- inside the interval, but not an estimate of the population.'],
    wuF_price_decile: ['價格十分位', 'price decile'],
    wuF_county_district: ['行政區', 'district'],
    wuF_county: ['縣市', 'county'],
    wuF_age_band: ['屋齡區間', 'age band'],
    wuF_size_band: ['坪數區間', 'size band'],
    wuF_has_mgr: ['有無管理員', 'manager or none'],
    wuF_district_x_price_decile: ['行政區 × 價格十分位', 'district x price decile'],
    wuF_district_x_age_band: ['行政區 × 屋齡區間', 'district x age band'],
    wuNoCell: ['沒有任何一格達到 %s 棟', 'no cell reaches %s buildings'],
    repP:       ['修繕費用按屋齡加權，而老公寓比較舊——所以這個設定有可能是自己造出結論。實測相反：改成不隨屋齡加權的固定比例，公寓的優勢反而變大（%s pp，原本 %s pp）。也就是說屋齡加權是比較保守的那個設定，不是比較有利的那個。',
                 'Repairs scale with age and walk-ups are older, so the spec could be manufacturing its own result. Measured, it goes the other way: under a FLAT rate the walk-up advantage gets bigger (%s pp against %s pp). Age-scaling is the conservative choice here, not the flattering one.'],
    repGross:   ['毛（純資料）', 'Gross (data only)'],
    repAge:     ['屋齡加權修繕', 'Age-scaled repairs'],
    repFlat:    ['固定比例修繕', 'Flat repairs'],

    covPunch:   ['所以任何用實價登錄算出來的租金報酬率，描述的都不是「臺灣的房市」，而是其中比較新、比較貴、比較常被拿來投資的那一小塊。這不是資料的瑕疵，這是資料的形狀——只要沒有人說出來，它就會被當成整個市場。',
                 'So any yield computed from this registry does not describe the Taiwanese housing market. It describes the newer, pricier, more investor-owned sliver of it. That is not a flaw in the data, it is the shape of the data -- and until someone says so, it gets read as the whole market.'],

    // ── districts ───────────────────────────────────────────────────────
    mapEy:      ['地圖', 'The map'],
    mapH:       ['%s 棟房子在哪裡', 'Where the %s buildings are'],
    mapP:       ['淡色的底層是所有有成交紀錄的建物（%s 棟，以 400 公尺網格呈現）；亮點是算得出報酬率的那 %s 棟。兩層的差距就是前面那個 %s%% 的空間版本。點任一個亮點看該棟明細，滑過看數字。',
                 'The faint layer is every building with a recorded sale (%s of them, on a 400 m grid). The bright points are the %s where a yield can be computed. The gap between the two layers is the spatial form of that %s%% figure. Click a point for the building, hover for the numbers.'],
    mapLegLow:  ['報酬率低', 'lower yield'],
    mapLegHigh: ['報酬率高', 'higher yield'],
    mapLegAll:  ['所有成交建物（密度）', 'all sold buildings (density)'],
    mapColor:   ['報酬率', 'YIELD'],
    mapTypeLbl: ['型態', 'TYPE'],
    // The heading and this sentence used to quote two different totals -- 9,118
    // from B.length and 10,148 from headline.buildings -- one line apart, on a
    // page whose whole pitch is that it shows you the shape of its own data.
    mapIntro:   ['其中 %s 棟對得到門牌坐標，可以標在地圖上；另外 %s 棟只出現在下方的表格。',
                 'Of these, %s have an address-point match and can be plotted; the other %s appear only in the table below.'],
    mapHow:     ['這個數字是怎麼算的、又看不到什麼？', 'How is this calculated, and what does it miss?'],
    mapClust:   ['棟', 'buildings'],
    mapNBld:    ['資料建物', 'Buildings'],
    mapClickDist:['點一下放大到這個行政區', 'Click to zoom to this district'],
    mapAll:     ['回到全部行政區', 'Back to all districts'],
    mapZoomHint:['點行政區看區內每一棟', 'Click a district to open every building in it'],
    layersBtn:  ['圖層', 'Layers'],
    filtBtn:    ['篩選', 'Filters'],
    filtBudget: ['總價上限', 'Max price'],
    filtYield:  ['報酬率下限', 'Min yield'],
    filtMrt:    ['距捷運', 'Within of MRT'],
    filtAny:    ['不限', 'Any'],
    filtClear:  ['清除', 'Clear'],
    filtOn:     ['%s 項篩選', '%s active'],
    filtShow:   ['符合 %s 棟', '%s buildings match'],
    pnlClose:   ['關閉', 'Close'],
    pnlGross:   ['毛報酬率', 'Gross yield'],
    pnlNet:     ['淨報酬率（依目前假設）', 'Net yield (current assumptions)'],
    pnlPrice:   ['成交價中位數', 'Median recorded sale'],
    pnlPPing:   ['每坪', 'Per ping'],
    pnlRent:    ['月租金中位數', 'Median monthly rent'],
    pnlBuilding:['建物', 'Building'],
    pnlType:    ['型態', 'Type'],
    pnlFloors:  ['總樓層', 'Floors'],
    pnlBuilt:   ['完工（民國）', 'Built (ROC)'],
    pnlAge:     ['屋齡', 'Age'],
    pnlMgr:     ['管理員', 'On-site staff'],
    pnlYes:     ['有', 'Yes'],
    pnlNo:      ['無', 'No'],
    pnlMarket:  ['周邊', 'Context'],
    pnlPairs:   ['買賣×租賃配對', 'Sale-lease pairs'],
    pnlMrt:     ['最近捷運站', 'Nearest MRT'],
    pnlYears:   ['年', 'yrs'],
    pnlNoVal:   ['這是已成交的登錄價格，不是估價。', 'This is a recorded transaction price, not a valuation.'],
    mapShape:   ['形狀＝建物型態', 'Shape = building type'],
    layRoads:   ['街道', 'Streets'],
    layMrt:     ['捷運', 'MRT'],
    layWater:   ['水域', 'Water'],
    layDens:    ['所有成交建物', 'All sold buildings'],
    layLabels:  ['地名', 'Labels'],
    noCoordsOld:['｜此區尚無門牌坐標檔，僅有數字',
                 '\u2502 no address-point file for this county yet — counts only'],
    noPairsOld: ['｜此區沒有同棟成交與出租的配對',
                 '\u2502 no same-building sale-and-lease pair here'],
    layZoomNote: ['街道、捷運與水域放大後才會出現',
                  'Streets, MRT and water appear as you zoom in'],
    // An average across a bimodal population: six counties sit above 98%% and
    // fourteen sit at exactly zero. Quoting the mean let a reader think the map
    // was nearly complete, then click a county and find it blank.
    mapGeo:    ['%s%% 的建物對得到門牌坐標（內政部門牌位置數值資料）。這是平均值，掩蓋了一個全有全無的分布：%s 個縣市在 98%% 以上，%s %s%%，另外 %s 個縣市政府尚未公開門牌位置檔，一棟都畫不出來。',
                 '%s%% of buildings match an address point (MOI data). That average hides an all-or-nothing split: %s counties are above 98%%, %s is at %s%%, and %s have no public address-point file and plot nothing.'],
    mapAttrib:  ['街道與捷運圖資 © OpenStreetMap 貢獻者（ODbL）；行政區界 內政部國土測繪中心。',
                 'Streets and MRT © OpenStreetMap contributors (ODbL); district boundaries from the Ministry of the Interior.'],
    mapZoom:    ['框選可放大，雙擊還原', 'Drag to zoom, double-click to reset'],
    mapReset:   ['還原', 'Reset'],
    mapGeoOld:  ['%s%% 的建物成功對到門牌坐標（內政部門牌位置數值資料）。',
                 '%s%% of buildings joined to a surveyed street-number coordinate (government address file).'],
    distEy:     ['行政區', 'By district'],
    distH:      ['報酬率最高的地方，不是房價最高的地方', 'The best yields are not where the prices are'],
    distP:     ['點任一行政區，下面的圖表與表格都會跟著篩選。橫線是該區中位數的 95%% 信賴區間，圓點是中位數。少於 %s 棟的行政區不列入。',
                 'Click a district to filter everything below. The line is the 95%% confidence interval on that district\'s median, the dot is the median. Districts with fewer than %s buildings are not shown.'],
    distAll:    ['全部行政區', 'All districts'],
    rankAllC:   ['全部縣市', 'All counties'],
    rankInto:   ['點縣市看區', 'Open a county to see its districts'],
    rankBack:   ['\u2190 回縣市', '\u2190 back to counties'],
    rankNone:   ['%s 沒有達到 %s 棟門檻的行政區。',
                 'No district in %s reaches the %s-building floor.'],

    // ── ladder (advanced) ───────────────────────────────────────────────
    ladEy:      ['清理的代價', 'What cleaning is worth'],
    ladH:       ['同一份資料，%s 種算法', 'One dataset, %s ways to count'],
    // The old copy said this table "measures one thing only: what each cleaning
    // decision is worth". It does not, and cannot: the sample is not nested the
    // way that sentence implies. Retracted, and replaced by the path/filter
    // split below.
    ladP:       ['每一階是「多做一道清理」之後的數字。這不是在說別人公布的是第一階——沒有人真的那樣算。要注意的是：這是一條「路徑」，不是每個篩選條件各自的價值。前一階改變了後一階要處理的樣本組成，所以某一階的變化量是「在前面都做完的前提下，這個條件值多少」。各條件本身值多少，看下面那張表。點任一階，上面的數字會跟著變。',
                 'Each rung applies one more cleaning step. This is NOT a claim that anyone publishes rung 1 -- nobody computes a yield that way. Read it as a PATH, not as the value of each filter: every rung changes the composition the next one acts on, so a rung\'s move is "this filter, given everything already applied". What each filter is worth on its own is the table below. Click a rung and the figure above follows it.'],
    fmH:        ['每個篩選條件各自值多少', 'What each filter is worth on its own'],
    fmP:        ['把三個條件的所有 6 種先後順序都跑一遍，取每個條件的平均邊際效果（Shapley 值）。三個加起來剛好等於總變化量，所以這是一個「分解」，不是三個各自獨立的敏感度測試。',
                 'Every one of the six possible orderings of the three filters, averaged, giving each filter its mean marginal effect (a Shapley value). The three sum exactly to the total move, which makes this a decomposition rather than three unrelated sensitivity checks.'],
    fmPath:     ['階梯上顯示的（以配對計）', 'As the ladder shows it (per pair)'],
    fmShapPair: ['與順序無關（以配對計）', 'Order-independent (per pair)'],
    fmShapBldg: ['與順序無關（以棟計）', 'Order-independent (per building)'],
    fmSocial:   ['排除社會住宅', 'Social housing removed'],
    fmRooms:    ['排除分租套房／雅房', 'Room-shares removed'],
    fmRelated:  ['排除親友間交易', 'Related-party sales removed'],
    fmWhy:      ['這張表是本站的一次更正。原本階梯顯示「排除社會住宅」讓報酬率下降 0.17pp——對一群租金比市場低 28% 的房子來說，方向是反的。原因不是篩選條件寫錯，是兩件事疊在一起：一，階梯前五階以「配對」計、後兩階以「棟」計，而社會住宅極度集中在少數幾棟包租代管的套房大樓，配對計會把它們的權重放大；二，排除社會住宅時分租套房還在樣本裡，而分租套房的報酬率只有約 1.3%（它的面積欄位記的是整棟不是出租單位），社會住宅裡幾乎沒有分租套房，所以一排除它，分租套房的佔比就變成三倍。統一以「棟」計、並把順序效果拆掉之後，方向就回來了：排除社會住宅讓報酬率上升。',
                 'This table is a correction. The ladder used to show "social housing removed" as -0.17pp -- the wrong direction for a population renting 28% below market. The filter was not wrong; two things were stacked on top of each other. First, mixed units: rungs 1-5 were medians over pairs and 6-7 over buildings, and social leases concentrate in a few very large 包租代管 studio towers, which a pair-level median over-weights. Second, ordering: social housing is removed while room-shares are still in the sample, and room-shares yield about 1.3% (their area field describes the building, not the let space). Social leases contain almost no room-shares, so removing social housing triples the room-share weight. Read in one unit and with the ordering effect stripped out, the sign returns: removing social housing RAISES the yield.'],
    fmLet:      ['出租型態', 'Letting type'],
    fmSoc:      ['社會住宅', 'Social'],
    fmMkt:      ['市場', 'Market'],
    fmMix:      ['佔各自樣本比例（社／市）', 'Share of each sample (social / market)'],
    fmConc:     ['集中度：有社會住宅租約的建物平均帶 %s 個配對，沒有的只帶 %s 個。以配對計時，前者被加權 %s:1；以棟計是 %s:1。',
                 'Concentration: a building holding any social lease carries %s pairs on average against %s for one that holds none. A pair-level median weights the first group %s:1; a building-level median weights it %s:1.'],
    ladNote:    ['整張表都以「棟」計算，每一列後面括號裡是同一階以「配對」計的數字。差別不小，而且是統計而非清理造成的：一棟有 40 筆買賣、30 筆租賃的大樓會產生 1,200 個配對，前十名建物就佔了全部配對的 %s%%。同一份最終樣本，以配對計是 %s%%，以棟計是 %s%%。以配對計會把少數幾棟巨型社區的權重放大到失真，所以本站所有數字都以「棟」為單位。',
                 'Every rung is read per building; the figure in brackets on each row is the same rung read per pair. The gap is large, and it is statistics rather than cleaning: a tower with 40 sales and 30 leases makes 1,200 pairs, and the top ten buildings alone are %s%% of all pairs. On the same final sample, per pair is %s%% and per building is %s%%. A pair-level median lets a handful of mega-developments dominate, so every number on this site is per building.'],
    rungPer:    ['以配對計 %s%%，%s 個配對', 'per pair %s%%, %s pairs'],
    rungPairs:  ['配對', 'pairs'],
    rungBldgs:  ['棟', 'buildings'],
    unitPair:   ['以配對計', 'per pair'],
    unitBldg:   ['以棟計', 'per building'],

    // ── rent bias (advanced) ────────────────────────────────────────────
    biasEy:     ['租金樣本', 'The rent sample'],
    // 82.1% is the share of WHOLE-UNIT residential leases; across all
    // registered leases it is nearer 58%.
    biasH:      ['登錄的整戶住宅租約裡，%s% 是社會住宅',
                 '%s% of registered whole-unit residential leases are social housing'],
    biasP:      ['台灣的租賃實價登錄只有透過房仲或包租業成交的案件要申報，而其中絕大多數是政府的社會住宅包租代管。這些租金是政策訂的，不是市場價——比市場租金低 %s%。任何沒有把它們排除掉的租金統計，量到的主要是社會住宅。',
                 'Only leases handled by an agency or a sublease operator must be registered -- and most of those are government social-housing programmes. Those rents are set by policy, not the market: %s% below market rent per ping. Any rent statistic that does not exclude them is mostly measuring social housing.'],
    biasSoc:    ['社會住宅租金', 'Social housing rent'],
    biasMkt:    ['市場租金', 'Market rent'],
    biasUnit:   ['元/坪/月', 'NT$/ping/mo'],

    // ── net yield (advanced) ────────────────────────────────────────────
    netEy:      ['淨報酬率', 'Net yield'],
    netH:       ['從毛報酬率扣到淨報酬率', 'From gross down to net'],
    netP:       ['這四項成本沒有一項在實價登錄裡。下面每個數字都可以調，調了整頁的淨報酬率就會跟著重算——因為這些是假設，不是量測，讀者應該可以自己決定。',
                 'None of these four costs is in the registry. Every number below is adjustable and the whole page recomputes when you move it -- because these are assumptions, not measurements, and the reader should own them.'],
    wfGross:    ['毛租金收入', 'Gross rent'],
    wfNote:     ['每一列是該項成本自己的中位數，最後一列是逐棟淨報酬率的中位數——中位數不可相加，所以把上面幾列相減不會剛好等於最後一列（本頁的資料上差約 %s pp）。第一列的毛報酬率是逐棟「年租金÷成交價」的中位數，與標題的 %s%%（以每坪租金÷每坪單價計）也有小幅差異。',
                 'Each row is the median of that cost on its own; the last row is the median of the per-building net yield. Medians are not additive, so subtracting the rows above does not land exactly on the last one (about %s pp apart on this data). The gross row is the median of annual rent over price per building, which differs slightly from the headline %s%%, computed from rent per 坪 over price per 坪.'],
    wfVac:      ['減 空置', 'less vacancy'],
    wfTax:      ['減 房屋稅＋地價稅', 'less holding tax'],
    wfMgmt:     ['減 管理費', 'less management'],
    wfRep:      ['減 修繕', 'less repairs'],
    wfNet:      ['淨報酬率', 'Net yield'],
    reset:      ['回復預設', 'Reset'],
    srcLabel:   ['來源', 'Source'],

    // ── dead hypothesis (advanced) ──────────────────────────────────────
    deadEy:     ['一個失敗的假設', 'A failed hypothesis'],
    deadH:      ['原本以為老公寓報酬率比較高。並沒有。', 'The prediction was that walk-ups out-yield towers. They do not.'],
    deadP:      ['這個專案原本的假設是：大樓要付管理費，公寓不用，所以公寓的淨報酬率會明顯比較高。實際上在毛報酬率（純資料）只差 %s 個百分點，等於沒有差。要到套上成本假設之後，差距才變成 %s 個百分點——也就是說，那個差距有 %s%% 是我自己的假設造出來的，不是台北的事實。這一段留在頁面上，因為後來那個真正的發現是在這個假設死掉之後才找到的。',
                 'The project set out to show that walk-ups out-yield towers, because towers pay management fees and walk-ups do not. At gross -- pure data -- the gap is %s pp, which is nothing. It only becomes %s pp after the cost model is applied. So %s%% of that gap is my assumption, not a fact about Taipei. This stays on the page because the real finding was only reached after this one died.'],
    deadEyA:    ['一個被更正的判定', 'A verdict that was corrected'],
    deadHA:     ['原本判定「公寓沒有比較高」。全國資料上，這個判定是錯的。',
                 'The verdict was that walk-ups do not out-yield towers. On national data, that verdict is wrong.'],
    deadPA:     ['這個專案原本的假設是：大樓要付管理費，公寓不用，所以公寓的淨報酬率會明顯比較高。涵蓋雙北時，毛報酬率的差距只有 0.041pp，等於沒有差——所以判定為「那個差距是我自己的成本假設造出來的」。改成全國尺度之後，毛差距是 %s pp%s，在任何成本模型介入之前就已經存在，扣成本後還擴大到 %s pp。原本那個判定是一個寫死在程式裡的字串，換了資料範圍之後從來沒有重新評估過。',
                 'The project set out to show that walk-ups out-yield towers, because towers pay management fees and walk-ups do not. Across Taipei and New Taipei the gross gap was 0.041pp -- nothing -- so the verdict was that the apparent gap came from my own cost assumptions. Nationally the gross gap is %s pp%s, present before any cost model is applied, and it WIDENS to %s pp after costs. The old verdict was a string hard-coded in the build, and it was never re-evaluated when the scope changed.'],
    deadCtl:    ['【但這不是一個乾淨的結果】原始差距 %s pp 會隨著「控制住什麼」而往兩個方向跑：在同一個價格分位內比，只剩 %s pp（%s 個可比分位，其中 %s 個是反向的，集中在最貴的那幾個）；在同一個行政區內比，反而是 %s pp（%s 個行政區，其中 %s／%s 個是公寓較高）。兩個不可能同時是「那個效果」。公寓位在較貴的行政區，但在那些行政區裡每坪比較便宜，而價格正是報酬率的分母——所以這裡量到的有相當一部分是「便宜的房子報酬率高」，不是「公寓比大樓好」。本站不宣稱已經把兩者分開。',
                 '[But this is not a clean result] The raw %s pp gap moves in opposite directions depending on what is held constant: within the same price decile it is %s pp (across %s comparable deciles, of which %s REVERSE, at the dear end), while within the same district it is %s pp (across %s districts, walk-ups ahead in %s of %s). Both cannot be the effect. Walk-ups sit in dearer districts but are cheaper per ping inside them, and price is the yield\'s denominator -- so a substantial part of what is measured here is "cheaper buildings yield more", not "walk-ups beat towers". This site does not claim to have separated the two.'],
    deadFix:    ['已修正：判定不再寫死，改由資料推導——毛差距的信賴區間若不含 0 就是「成立」，含 0 才是「已死」。同時補上信賴區間。一個不會因為資料改變而改變的結論，不是結論。',
                 'Fixed: the verdict is no longer hard-coded. It is derived -- the hypothesis stands if the confidence interval on the gross gap excludes zero, and dies only if it contains zero -- and the interval is now published. A conclusion that cannot change when the data changes is not a conclusion.'],
    deadGross:  ['毛報酬率差距（資料）', 'Gross gap (data)'],
    deadNet:    ['淨報酬率差距（含假設）', 'Net gap (with assumptions)'],
    byType:     ['依建物型態', 'By building type'],
    byMgr:      ['依有無管理員（實際登錄欄位）', 'By observed on-site management'],

    // ── scatter (advanced) ──────────────────────────────────────────────
    scatEy:     ['每一棟', 'Every building'],
    scatH:      ['%s 棟房子，各自的價格與租金', '%s buildings, each with its own price and rent'],
    scatP:      ['橫軸每坪成交價，縱軸每坪年租金。斜虛線是等報酬率線：越靠左上，報酬率越高。',
                 'Price per ping across, annual rent per ping up. The dashed diagonals are iso-yield lines: up and to the left is a higher yield.'],
    scatX:      ['每坪成交價（萬元）', 'Price per ping (NT$10k)'],
    scatY:      ['每坪年租金（元）', 'Annual rent per ping (NT$)'],
    scatDrop:   ['%s 棟超出座標範圍未繪出。是刪掉不是壓到邊界——壓到邊界會在軸線上長出一團假的群聚。',
                 '%s buildings fall outside the axes and are dropped, not clamped. Clamping would grow a fake cluster on the boundary.'],

    // ── method checks (advanced) ────────────────────────────────────────
    mcEy:       ['方法檢查', 'Method checks'],
    mcH:        ['一個沒有成功的修正，和它背後的分布',
                 'One correction that did not work, and the distribution behind it'],
    histH:      ['報酬率的分布', 'How the yields spread'],
    histLeg:    ['實心＝毛報酬率（中位數 %s%%），外框＝扣掉成本後（%s%%）。兩條虛線是兩個中位數，中間的距離就是成本模型。',
                 'Filled = gross (median %s%%); outline = after costs (%s%%). The two dashed lines are those medians, and the distance between them is the cost model.'],
    histNetN:   ['扣掉成本後仍有 %s%% 的建物落在 1%% 以下，%s 棟為負。這是本站的預設假設，不是市場事實——成本那一節的滑桿會改變這張圖。',
                 'After costs, %s%% of buildings sit below 1%% and %s below zero. That is this site\'s default assumptions, not a fact about the market -- the sliders in the cost section move this chart.'],
    histX:      ['報酬率 %', 'Yield %'],
    // The build clips values into range before binning (underwrite.histogram
    // uses v.clip(lo, hi)), so both end buckets are pile-ups, not counts of
    // their own interval. The right-hand spike is real and it is an artefact.
    histClip:   ['兩端的長條是「堆積」而不是區間本身：超出範圍的值會被夾到最外側的桶裡，所以最右邊那根包含所有更高的報酬率。',
                 'The end bars are pile-ups, not counts of their own interval: values outside the range are clipped into the outermost bucket, so the right-hand bar holds every higher yield as well.'],
    gapH:       ['配對間隔會不會偷渡房價漲幅？', 'Does the pairing window smuggle in price drift?'],
    gapP:       ['買賣與租賃最多相隔 4 季。如果殘留斜率是房價漲幅造成的，用價格指數校正就該把它壓平。實測是壓不平、反而更陡（下表），所以它不是漲幅，是組成差異：買賣與租賃相隔越久的建物，本來就是比較冷門的那一批。價格指數因此關閉。',
                 'A sale and a lease may sit up to 4 quarters apart. If the residual slope were price drift, a price index would flatten it. Measured, it steepens it (table below) -- so the slope is not drift but composition: buildings whose sale and lease sit far apart are the thinner, less-traded ones. The index is therefore switched OFF.'],
    gapX:       ['配對間隔（季）', 'Pairing gap (quarters)'],
    idxH:       ['價格指數校正：實測結果', 'Price index: measured result'],
    idxWin:     ['配對窗', 'Window'],
    idxIdx:     ['價格指數', 'Price index'],
    idxSlope:   ['殘留斜率', 'Residual slope'],
    idxOn:      ['開', 'on'],
    idxOff:     ['關', 'off'],

    // ── table ───────────────────────────────────────────────────────────
    tblEy:      ['資料', 'The data'],
    tblH:       ['每一棟的明細', 'Every building, itemised'],
    tblP:       ['可搜尋地址、排序、依行政區與型態篩選。', 'Search the address, sort any column, filter by district and type.'],
    thAddr:     ['地址', 'Address'],
    thDist:     ['行政區', 'District'],
    thType:     ['型態', 'Type'],
    thYield:    ['毛報酬率', 'Gross'],
    thNet:      ['淨報酬率', 'Net'],
    thPrice:    ['每坪價', 'Price/ping'],
    thRent:     ['每坪年租', 'Rent/ping/yr'],
    thPairs:    ['配對', 'Pairs'],
    thBuilt:    ['完工', 'Built'],
    search:     ['搜尋地址…', 'Search address...'],
    showing:    ['顯示 %s 棟', 'Showing %s buildings'],
    allTypes:   ['全部型態', 'All types'],

    // ── limits / method ─────────────────────────────────────────────────
    moiEy:      ['對照官方數字', 'Against the official figures'],
    moiH:       ['政府自己的數字，放在本站旁邊', 'The government\'s own numbers, beside this site\'s'],
    moiP:       ['以下每一個官方數字都來自內政部不動產資訊平台，跟本站的算法無關。放在一起看的目的不是取代，是對照：官方的、本站的、以及兩者之間的落差——而那個落差，跟本頁其他每一節從實價登錄內部得到的結論，是同一件事。',
                 'Every official figure below comes from the MOI Real Estate Information Platform and has nothing to do with this site\'s method. They are here to be set beside ours, not to replace them: theirs, ours, and the gap between -- and the gap is the same finding every other section reaches from inside the registry, now reached from outside it.'],
    moiStockH:  ['分母背後的分母', 'The denominator behind the denominator'],
    moiUniv:    ['本站的分母：十一季內有買賣紀錄的住宅建物', 'This site\'s denominator: residential buildings with a sale in the window'],
    moiMatched: ['本站算得出報酬率的建物', 'Buildings this site can price'],
    moiStockN3: ['住宅存量 %s 宅（%s）；房屋稅籍住宅類 %s 宅（%s）。兩個數字期別不同，不相減。',
                 'Housing stock %s dwellings (%s); %s residential units on the house-tax roll (%s). Different periods -- set side by side, never differenced.'],
    moiStockN2: ['住宅存量 %s 宅（%s）；房屋稅籍住宅類 %s 宅（%s）。兩個數字期別不同，不相減。本站原本在這裡寫「每 1,086 棟裡一棟」，那是把棟除以建號，已撤回。',
                 'Housing stock %s dwellings (%s); %s residential units on the house-tax roll (%s). Different periods -- set side by side, never differenced. This section used to say "one building in 1,086" here; that divided buildings by 建號 and is withdrawn.'],
    moiStockN:  ['住宅存量（以宅計，不是以棟計，所以不能直接相除）：%s 宅，%s。建物總量含非住宅用途，所以上面的比例是「所有建物」的比例，不是「所有住宅」的。',
                 'Housing stock, in dwellings rather than buildings so it cannot be divided directly: %s at %s. Building stock includes non-residential uses, so the ratios above are of ALL buildings, not of all homes.'],
    moiPriceH:  ['官方每坪均價 vs 本站配對建物中位數', 'Official price per 坪 vs this site\'s matched median'],
    moiPriceP:  ['%s 那一季，內政部公布的各縣市買賣契約平均單價（全部建物類型），對照本站在同一縣市能算出報酬率的建物的每坪中位數。',
                 'For %s, the MOI\'s published mean contract price per 坪 by county (all building types), against the median price per 坪 across the buildings this site can price in the same county.'],
    moiOfficial:['官方均價', 'Official mean'],
    moiOurs:    ['本站中位數', 'Our median'],
    moiGap:     ['本站高出', 'Ours above'],
    moiPriceWhy:['在樣本較大的 %s 個縣市，本站的配對建物中位數比官方均價高 %s%%。這不是計算錯誤，是本頁的核心發現從外部再看一次：能同時被賣掉又被登錄出租的房子，是比較新、比較貴、比較多電梯大樓的那一群。官方數字把所有房子都算進去了；本站只看得到那一群。',
                 'Across the %s counties with the largest samples, this site\'s matched median sits %s%% above the official mean. That is not an error; it is the page\'s central finding seen from outside: the buildings that both sell and get let on the registry are the newer, dearer, tower-heavy slice. The official figure counts every home; this site can only see that slice.'],
    moiIdxH:    ['官方房價指數 vs 本站沒有修正的那一段', 'The official price index vs the drift this site leaves in'],
    moiIdxWin:  ['官方住宅價格指數，%s → %s', 'Official house-price index, %s to %s'],
    moiIdxDrift:['本站中位數配對相隔 %s 季，在這段時間裡房價大約動了這麼多',
                 'What prices moved across this site\'s median pair gap of %s quarters'],
    moiIdxP:    ['本站自己算的地區房價指數量過、讓結果更差、已經關掉。這留下一個承認了但沒量化的限制：一筆買賣和一筆租賃可以相隔四季，中間的房價變動沒有被修正。內政部的住宅價格指數給了它一個數字：從 %s 到 %s，%s 季，合計每季 %s%%。本站配對的中位數間隔是 %s 季，所以一個典型的配對大約帶著 %s%% 未修正的房價變動。這就是被留在裡面的東西的真實大小。',
                 'This site\'s own district price index was measured, made things worse, and is off. That leaves an admitted, unquantified limitation: a sale and a lease may sit four quarters apart and nothing corrects for prices moving in between. The MOI index puts a number on it: %s to %s over %s quarters, %s%% a quarter. This site\'s median pair gap is %s quarters, so a typical pair carries about %s%% of uncorrected price movement. That is the honest size of what is left in.'],
    moiLuH:     ['空屋，放在空置率假設旁邊', 'Empty homes, beside the vacancy assumption'],
    moiLuP:     ['%s，內政部以用電量認定的低度使用住宅佔全國房屋稅籍住宅類數量 %s%%（與內政部公布的比率同一個分母）。本站的成本模型假設 %s%% 的空置率——那是一個假設，而且這兩個數字不是同一件事，下面會解釋。',
                 'In %s, dwellings the MOI classes as low-use by electricity consumption were %s%% of residential units on the house-tax roll -- the same base the MOI publishes its own rate on. This site\'s cost model assumes %s%% vacancy -- an assumption, and the two numbers are not the same thing, as explained below.'],
    moiLuN:     ['低度使用住宅', 'Low-use dwellings'],
    moiLuStock: ['房屋稅籍住宅類', 'Tax-roll residential units'],
    moiLuRate:  ['比例', 'Rate'],
    moiLuWhy:   ['這不是空置率的輸入值，也不能拿來替換那個 5%%。低度使用住宅算的是「幾乎沒用電的房子」——第二個家、待售的房子、換手中的房子都在裡面——分母是全部住宅，不是出租住宅。租屋空置率問的是「出租的房子裡有多少沒租出去」，分母不同、分子也不同。臺灣沒有這個統計，所以本站的 5%% 仍然是假設。這張表能做的，是讓下面那個損益兩平測試有東西可以對照。',
                 'This is not a vacancy input and cannot replace the 5%%. Low-use counts every dwelling drawing almost no electricity -- second homes, homes for sale, homes between owners -- over ALL dwellings, not rental stock. Rental vacancy asks how many of the homes that are let sit unlet; different numerator, different denominator. Taiwan publishes no such statistic, so this site\'s 5%% stays an assumption. What this table does is give the break-even test below something to stand against.'],
    moiLuVb:    ['對照：%s%s 要掉到全國中位數，空置率得達到 %s%%；而 %s 以用電量認定的低度使用住宅比例是 %s%%。',
                 'For scale: %s%s would need %s%% vacancy to fall to the national median, and %s\'s low-electricity-use share of dwellings is %s%%.'],
    moiUnsold:  ['另一個本頁算不出報酬率的存量：內政部登記的待售新成屋有 %s 宅（%s）——蓋好了、還沒賣掉、也還沒人住，跟預售屋那一節講的是同一塊看不見的市場。',
                 'Another stock this page cannot price: the MOI counts %s completed new homes still unsold (%s) -- built, not yet sold, not yet lived in, the same unseen market the pre-sale section describes.'],
    moiAucH:    ['法拍：本站看不到的那個管道，有多大', '法拍: how big the channel this site cannot see is'],
    moiCourt:   ['法院拍定件數（內政部）', 'Court-auction lots (MOI)'],
    moiFasc:    ['金拍件數（本站的資料來源）', '金拍 lots (this site\'s feed)'],
    moiAucP:    ['本站的拍賣資料來源是金拍（銀行透過台灣金服處分擔保品），不是法院拍賣。法院拍賣大得多。多大？同一個十一季的窗口裡，內政部登記的法院拍定成屋有 %s 件（%s 季，拍定總額約 %s 億元）。本站的金拍資料來源是 %s 件——大約是法拍件數的 %s%%。兩個是平行的管道，不是包含關係。',
                 'This site\'s auction feed is 金拍 -- banks disposing of collateral through TFASC -- not court auctions, which are much larger. How much: in the same eleven-quarter window the MOI records %s completed court-auction sales (%s quarters, about NT$%s hundred million in total). This site\'s 金拍 feed carries %s lots -- roughly %s%% as many. The two are parallel channels, not one inside the other.'],
    moiAucP0:   ['本站的拍賣資料來源是金拍（銀行透過台灣金服處分擔保品），不是法院拍賣。法院拍賣大得多。多大？十一季的窗口裡，內政部登記的法院拍定成屋有 %s 件（%s 季，拍定總額約 %s 億元）。本站的金拍資料來源共 %s 件（未限定在同一窗口）——大約是法拍件數的 %s%%。兩個是平行的管道，不是包含關係。',
                 'This site\'s auction feed is 金拍 -- banks disposing of collateral through TFASC -- not court auctions, which are much larger. How much: in the eleven-quarter window the MOI records %s completed court-auction sales (%s quarters, about NT$%s hundred million). This site\'s 金拍 feed carries %s lots in total (not restricted to the same window) -- roughly %s%% as many. Parallel channels, not one inside the other.'],
    moiAucTop:  ['法拍件數最多的縣市：%s。', 'Most court-auction lots: %s.'],
    moiMort:    ['利率的第二個官方來源：內政部「本季新增購置住宅貸款平均利率」%s%%（%s），對照本頁引用的央行五大銀行新承做購屋貸款 %s%%（%s）。兩者衡量的對象不同，故並列不取代。',
                 'A second official rate: the MOI\'s average on new house-purchase loans, %s%% (%s), beside the Central Bank\'s five-bank rate this page cites, %s%% (%s). They measure different populations, so both are shown and neither replaces the other.'],
    limEy:      ['這份資料不能告訴你什麼', 'What this cannot tell you'],
    limH:       ['先看清楚邊界', 'The boundaries, up front'],
    lim1:       ['只涵蓋有成交紀錄的建物中的 %s%。看不到沒賣過或沒登錄出租的房子。',
                 'Covers %s% of buildings with a recorded sale. Anything that has not sold, or was never registered as let, is invisible.'],
    lim2:       ['只有 %s 季（民國 %s 到 %s）。看不出景氣循環，也不該拿來預測。',
                 'Only %s quarters (ROC %s to %s). Too short to show a cycle and not a forecast.'],
    lim3:       ['租賃紀錄本身就偏：個人房東直接出租不用申報，只有透過房仲或包租代管業成交的才要登錄。這份資料算不出「有多少租屋沒進來」——那需要外部的租屋總量統計，本站沒有引用，所以不寫一個數字。這份資料能算出來的是：已登錄的整戶租約裡有 %s%% 是社會住宅包租代管。',
                 'The lease side is skewed by law: a landlord letting directly reports nothing, and only agency- or operator-handled lettings must be registered. This dataset cannot say what share of the rental market is missing -- that needs an external estimate of the total, which this site does not cite, so no figure is given. What it can say is that %s%% of the whole-unit leases that ARE registered are social-housing sublease or management.'],
    lim4:       ['報酬率不是報酬。沒有貸款、沒有增值、沒有交易稅費，也沒有任何一間房子的未來。',
                 'A yield is not a return. No mortgage, no capital gain, no transaction taxes, and no claim about the future of any building.'],
    methEy:     ['方法', 'Method'],
    methH:      ['這個數字是怎麼算出來的', 'How the number is made'],
    src:        ['資料來源', 'Source'],
    srcV:       ['內政部不動產成交案件實際資訊資料供應系統（實價登錄）',
                 'Ministry of the Interior actual-price registry (實價登錄)'],
    lic:        ['授權', 'Licence'],
    win:        ['期間', 'Window'],
    winV:       ['民國 %s 至 %s，共 %s 季', 'ROC %s to %s, %s quarters'],
    addrOk:     ['地址正規化', 'Address normalisation'],
    addrOkV:    ['%s%% 的紀錄沒有可用門牌（其餘全部可解析）。同棟比對以正規化後的門牌為鍵。',
                 '%s%% of records carry no usable street number; every other record parses. Matching keys on the normalised 門牌.'],
    whyWin:     ['為什麼不是五年', 'Why not five years'],
    whyWinV:    ['租賃資料的六個欄位（出租型態、租賃住宅服務、有無管理員…）到 112S4 才出現。少了它們就無法排除社會住宅與分租套房，硬接更早的資料會做出一條假的時間趨勢。',
                 'Six lease columns (出租型態, 租賃住宅服務, 有無管理員 and others) only exist from season 112S4. Without them social housing and room-shares cannot be excluded, and splicing earlier data would manufacture a fake time trend.'],
    filters:    ['清理規則', 'Cleaning rules'],
    f1:         ['只取住宅：住宅大樓、華廈、公寓。「主要用途為住家用」這個條件只套在買賣端——租賃端的登錄有相當比例主要用途不是住家用（商業用、一般事務所等），兩邊並不對稱。',
                 'Residential only: towers, mid-rises and walk-ups. The 主要用途 = 住家用 condition is applied to the SALE side only -- a sizeable share of the kept leases carry a non-住家用 main use (商業用, 一般事務所 and similar), so the two sides are not symmetric here.'],
    f2:         ['車位用「扣除」而非「整筆排除」：含車位的交易保留，但用實價登錄逐筆列明的車位價格與面積（*_park.csv）把車位扣掉，只有登錄機關沒有列明的才整筆丟掉。兩邊並不完全相同：買賣端若車位價格未列明就整筆丟掉，租賃端則保留，並推算一筆車位租金扣除（同棟有列明者的中位數，否則縣市、否則全國）——v2.0 以前只調整面積，前提是零代表免費；這個前提本站已在同棟內檢驗，結果不成立，見「清理的代價」末段的車位租金檢驗。整筆排除是本站的舊作法，兩者的差距就是階梯的最後一階。',
                 'Parking is SUBTRACTED, not excluded whole: a transaction carrying a space is kept, with the space removed using the price and area the registry itemises for it (*_park.csv), and only rows the registry failed to itemise are dropped. The two sides are not treated identically: on the sale side a row with no itemised parking price is dropped, while on the lease side it is kept and an imputed space rent is subtracted (the same building\'s itemised median, else the county\'s, else the country\'s) -- before v2.1 only its area was adjusted, on the assumption that a zero meant a free space; this site tested that within building and found it false (see the parking-rent audit at the foot of the ladder section). Dropping the whole transaction was this site\'s earlier method -- the difference between the two is the last rung of the ladder.'],
    f3:         ['排除社會住宅包租代管——租金由政策設定。',
                 'Social-housing sublease and management removed: those rents are set by policy.'],
    f4:         ['排除分租套房與雅房——它們的建物面積是整層或整棟，不是出租的那一間。',
                 'Room-shares removed: their floor area is the whole floor or building, not the let space.'],
    f5:         ['以「棟」為分析單位，不是配對數。', 'The unit of analysis is the building, never the pair.'],
    f6:         ['價格指數校正實測無效，已關閉（見方法檢查）。',
                 'The price-index correction was measured, did not work, and is off.'],
    legal:      ['這是對已完成公開交易的統計描述，不是對任何特定不動產的估價。',
                 'These are descriptive statistics on completed public transactions. Nothing here is an appraisal of any particular property.'],
    footNote:   ['本頁所有數字由公開資料計算，可完全重現。',
                 'Every number on this page is computed from open data and is fully reproducible.'],
    loading:    ['載入中…', 'Loading...'],
    failed:     ['資料載入失敗。請先執行 python underwrite.py 產生 housing_data.json。',
                 'Could not load data. Run python underwrite.py to generate housing_data.json.']
  };

  function S(k) { var v = STR[k]; return v ? v[LANG === 'zh' ? 0 : 1] : k; }
  function Sf(k) {
    // %% is an escaped literal percent. Without this branch every string that
    // needed a trailing "%" after a substitution rendered it as "3.66%%" --
    // in eight places, because the STR table was written as if Python were
    // doing the formatting.
    var s = S(k), a = Array.prototype.slice.call(arguments, 1), i = 0;
    return s.replace(/%[s%]/g, function (m) {
      return m === '%%' ? '%' : a[i++];
    });
  }

  // ── formatting ────────────────────────────────────────────────────────
  function pct(v, d) { return v == null ? '--' : v.toFixed(d == null ? 2 : d) + '%'; }
  function n0(v) { return v == null ? '--' : Math.round(v).toLocaleString('en-US'); }
  // The reference-rate strip. Mortgage keeps the three decimals it already
  // shows; the two new rates are quoted to two, their published precision.
  function bmOf(k) {
    var B = D.benchmarks || [];
    for (var i = 0; i < B.length; i++) if (B[i].key === k) return B[i];
    return null;
  }
  function bmFmt(b) { return b.key === 'mortgage' ? b.rate.toFixed(3) : b.rate.toFixed(2); }
  function bmPeriod(b) { return LANG === 'zh' ? b.period_zh : b.period_en; }
  function money(v) {
    if (v == null) return '--';
    if (LANG === 'zh') return (v / 10000).toFixed(1) + '萬';
    return 'NT$' + Math.round(v).toLocaleString('en-US');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function typeLabel(t) { return LANG === 'zh' ? t : (TYPE_EN[t] || t); }
  // The fill a 建物型態 gets in a chart. Three textures, not three tones — a
  // stacked segment has no room for a label, so the mark itself has to say
  // which type it is, and it must do that without borrowing the density
  // channel that yield is using.
  function typeHatch(t) { var i = TYPES.indexOf(t); return 'url(#hxt' + (i < 0 ? 1 : i + 1) + ')'; }

  // 建物型態 used to be carried by three colours AND by three shapes at the
  // same time. With one ink the colours all collapse to the same value, so the
  // shape has to carry it alone everywhere — not just on the map, where
  // symbolPath() has always drawn 公寓 as a circle, 華廈 as a diamond and
  // 住宅大樓 as a square. Anywhere a swatch used to stand in for a type, it is
  // now that same mark, so the reader learns one vocabulary rather than two.
  function typeMark(t, px) {
    var r = (px || 12) / 3.15;
    return '<svg class="hs-tmark" width="' + (px || 12) + '" height="' + (px || 12) +
      '" viewBox="-6 -6 12 12" aria-hidden="true" focusable="false">' +
      symbolPath(t, 0, 0, r) + ' fill="var(--text)"/></svg>';
  }

  // ── the cost model: TWIN of net_yield() in underwrite.py ───────────────
  function asm() {
    if (state.asm) return state.asm;
    var o = {};
    (D.assumptions || []).forEach(function (a) { o[a.key] = a.default; });
    state.asm = o;
    return o;
  }
  function netYield(b, a, mode) {
    a = a || asm();
    if (!b.pa || !b.rm) return null;
    var annual = b.rm * 12;
    // The shape multiplier is opt-in: the headline, the PDF and the Python
    // twin all charge the flat level, so applying b.vs by default would put
    // the page and underwrite.py out of lockstep on the headline itself.
    var vac = a.vacancy * (state.vshape && b.vs ? b.vs : 1);
    var effective = annual * (1 - vac / 100);
    var mgmtRate = b.c === 'a' ? a.mgmt : a.mgmt * (105 / 140);
    // mode 'flag': charge the fee only where a lease says the rent includes
    // it (b.mf). The Python twin has no such argument -- its flag-only bound
    // applies the charge vector outside net_yield -- so do not "fix" the
    // asymmetry by adding one there; it would touch the headline path.
    var mgmt = b.m ? ((mode === 'flag' && !b.mf) ? 0 : mgmtRate * b.ar * 12) : 0;
    var tax = b.pa * a.tax / 100;
    var age = b.b == null ? 0 : Math.max(0, 115 - b.b);
    var repairs = annual * (a.repairs / 100) * (1 + age / 50);
    return (effective - mgmt - tax - repairs) / b.pa * 100;
  }
  function medianOf(arr) {
    var v = arr.filter(function (x) { return x != null && isFinite(x); }).sort(function (x, y) { return x - y; });
    if (!v.length) return null;
    var m = Math.floor(v.length / 2);
    return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
  }

  // ── a deterministic bootstrap, so the intervals are reproducible ──────
  //
  // Seeded on purpose: an interval that moves every time the page loads is not
  // a number anyone can check against, and this whole page is an argument for
  // checking. Buildings are already the unit here (the payload ships one row
  // per building), so this is a one-stage cluster bootstrap -- the two-stage
  // version in the build exists because it starts from pairs.
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  // Quickselect rather than a sort per replicate: 200 sorts of a 2,000-element
  // bin is enough work to be felt on a phone, and only the median is wanted.
  function selectK(a, k) {
    var lo = 0, hi = a.length - 1;
    while (lo < hi) {
      var p = a[(lo + hi) >> 1], i = lo, j = hi;
      while (i <= j) {
        while (a[i] < p) i++;
        while (a[j] > p) j--;
        if (i <= j) { var t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
      }
      if (k <= j) hi = j; else if (k >= i) lo = i; else break;
    }
    return a[k];
  }
  function medianIn(a) {
    var n = a.length, h = n >> 1, v = selectK(a, n % 2 ? h : h - 1);
    if (n % 2) return v;
    var mn = Infinity;
    for (var i = h; i < n; i++) if (a[i] < mn) mn = a[i];
    return (v + mn) / 2;
  }
  var BOOT_REPS = 200, BOOT_MIN_N = 25;
  function bootCI(vals, seed) {
    var clean = [];
    for (var i = 0; i < vals.length; i++) {
      if (vals[i] != null && isFinite(vals[i])) clean.push(vals[i]);
    }
    var n = clean.length;
    if (n < BOOT_MIN_N) return null;
    var rnd = mulberry32(seed >>> 0), out = new Float64Array(BOOT_REPS);
    var buf = new Float64Array(n);
    for (var r = 0; r < BOOT_REPS; r++) {
      for (var j = 0; j < n; j++) buf[j] = clean[(rnd() * n) | 0];
      out[r] = medianIn(buf);
    }
    var s = out.slice().sort();
    function q(p) { return s[Math.min(BOOT_REPS - 1, Math.max(0, Math.round(p * (BOOT_REPS - 1))))]; }
    return { lo: q(0.025), hi: q(0.975) };
  }

  // Chart width for a horizontal bar chart: its natural width on a desktop,
  // the viewport on a phone. These charts label each bar at its END, so when
  // they were left at natural width and allowed to scroll, the longest bar --
  // the -72.2pp that is the whole point of the waterfall -- was the one cut
  // off. Bar length scales with W; the text does not, so labels stay 11px.
  var _MOBILE_W = 900;
  function chartW(natural) {
    var vw = window.innerWidth || natural;
    if (vw > _MOBILE_W) return natural;
    // viewport minus the page gutter (2 x 16) and the card padding (2 x 24).
    // vw - 40 left the chart 40px wider than the card's content box, and every
    // card reported a horizontal scroll for a chart that did fit.
    return Math.max(280, Math.min(natural, vw - 80));
  }

  // ── tiny SVG helpers ──────────────────────────────────────────────────
  function svg(w, h, body, cls, label) {
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="' + w + '" height="' + h +
      (label ? '" role="img" aria-label="' + esc(label) : '" aria-hidden="true') +
      '" class="' + (cls || '') + '" preserveAspectRatio="xMinYMin meet">' + body + '</svg>';
  }
  function line(x1, y1, x2, y2, stroke, sw, extra) {
    return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 +
      '" stroke="' + stroke + '" stroke-width="' + (sw || 1) + '"' + (extra || '') + '/>';
  }
  // A row label that lives in a left gutter. Where the gutter cannot hold it,
  // put it ABOVE the bar rather than letting the SVG clip its head off -- the
  // pattern secPartialId's ladder uses. Latin text is far wider than the same
  // sentence in Chinese, so the English page clipped where the Chinese did not,
  // in three charts at phone width and in the volume panels at EVERY width.
  function rowLabel(gutterX, y, text, gutter, opts) {
    var wide = String(text).length * (LANG === 'zh' ? 12.5 : 7.0);
    if (wide <= gutter - 8) return txt(gutterX, y, text, 'hs-glab', 'end', opts || '');
    return txt(2, y - 14, text, 'hs-glab', 'start', opts || '');
  }

  function txt(x, y, s, cls, anchor, extra) {
    return '<text x="' + x + '" y="' + y + '" class="' + (cls || '') + '" text-anchor="' +
      (anchor || 'start') + '"' + (extra || '') + '>' + esc(s) + '</text>';
  }
  function rect(x, y, w, h, fill, extra) {
    return '<rect x="' + x + '" y="' + y + '" width="' + Math.max(0, w) + '" height="' +
      Math.max(0, h) + '" fill="' + fill + '"' + (extra || '') + '/>';
  }
  function ticks(lo, hi, n) {
    var step = (hi - lo) / n, out = [];
    for (var i = 0; i <= n; i++) out.push(lo + step * i);
    return out;
  }
  function legend(items) {
    return '<div class="hs-legend">' + items.map(function (t) {
      return '<b>' + typeMark(t, 12) +
        esc(typeLabel(t)) + '</b>';
    }).join('') + '</div>';
  }

  // ── tooltip ───────────────────────────────────────────────────────────
  var tip;
  function tipShow(html, x, y) {
    if (!tip) return;
    tip.innerHTML = html;
    tip.classList.add('on');
    var r = tip.getBoundingClientRect();
    tip.style.left = Math.min(Math.max(8, x + 14), window.innerWidth - r.width - 8) + 'px';
    var top = y - r.height - 14;
    tip.style.top = (top < 8 ? y + 20 : top) + 'px';
  }
  function tipHide() { if (tip) tip.classList.remove('on'); }
  function kv(k, v) {
    return '<div><span class="k">' + esc(k) + '</span> <span class="v">' + esc(v) + '</span></div>';
  }

  // 實價登錄 keys its county files a..z, and the MOI boundary shapefile's
  // COUNTYID is the SAME letter — verified against all 368 records, 22 for 22.
  // That is why nothing in the pipeline hard-codes a county list any more.
  // Short English names because the district chart has ~40 px for this column.
  var COUNTY = {
    a: ['臺北市', 'Taipei'],      b: ['臺中市', 'Taichung'],   c: ['基隆市', 'Keelung'],
    d: ['臺南市', 'Tainan'],      e: ['高雄市', 'Kaohsiung'],  f: ['新北市', 'N.Taipei'],
    g: ['宜蘭縣', 'Yilan'],       h: ['桃園市', 'Taoyuan'],    i: ['嘉義市', 'Chiayi C.'],
    j: ['新竹縣', 'Hsinchu Co.'], k: ['苗栗縣', 'Miaoli'],     m: ['南投縣', 'Nantou'],
    n: ['彰化縣', 'Changhua'],    o: ['新竹市', 'Hsinchu C.'], p: ['雲林縣', 'Yunlin'],
    q: ['嘉義縣', 'Chiayi Co.'],  t: ['屏東縣', 'Pingtung'],   u: ['花蓮縣', 'Hualien'],
    v: ['臺東縣', 'Taitung'],     w: ['金門縣', 'Kinmen'],     x: ['澎湖縣', 'Penghu'],
    z: ['連江縣', 'Lienchiang']
  };
  function countyEn(c) { return (COUNTY[c] && COUNTY[c][1]) || String(c || '').toUpperCase(); }
  function countyName(c) { return (COUNTY[c] && COUNTY[c][LANG === 'zh' ? 0 : 1]) || c; }

  // ── filtering ─────────────────────────────────────────────────────────
  // Memoised: the hover path used to re-filter 2,549 records on every
  // pointermove. The key is every input that can change the result.
  var _fCache = null, _fKey = null;
  function filtered() {
    var key = [state.district, state.type, state.q, state.maxPrice,
               state.minYield, state.maxMrt].join('|');
    if (_fKey === key && _fCache) return _fCache;
    _fKey = key;
    _fCache = D.buildings.filter(function (b) {
      // county|district, never the bare name. Eight district names are shared
      // across counties -- there is a 大安區 in BOTH 臺北市 and 臺中市, and a
      // 中正區/中山區/信義區 in both 基隆市 and 臺北市 -- so filtering on the name
      // alone silently merges two cities into one row of results.
      if (state.district && b.c + '|' + b.d !== state.district) return false;
      if (state.type && b.t !== state.type) return false;
      if (state.q && b.a.indexOf(state.q) < 0) return false;
      if (state.maxPrice && b.pa > state.maxPrice) return false;
      if (state.minYield && b.y < state.minYield) return false;
      if (state.maxMrt && (b.mrt == null || b.mrt > state.maxMrt)) return false;
      return true;
    });
    return _fCache;
  }

  // A buyer's first two questions are "what can I afford" and "what does it
  // return" -- neither was answerable before. Budget is in 萬 because that is
  // the unit every Taiwanese listing quotes.
  function mapFilters() {
    var n = (state.maxPrice ? 1 : 0) + (state.minYield ? 1 : 0) + (state.maxMrt ? 1 : 0);
    var priceOpts = [[null, S('filtAny')], [15000000, '1,500萬'], [25000000, '2,500萬'],
                     [40000000, '4,000萬'], [60000000, '6,000萬'], [100000000, '1億']];
    var yieldOpts = [[null, S('filtAny')], [2, '2%'], [2.5, '2.5%'], [3, '3%'], [4, '4%']];
    var mrtOpts = [[null, S('filtAny')], [300, '300m'], [500, '500m'], [800, '800m'], [1500, '1.5km']];
    function sel(id, opts, cur, fmt) {
      return '<select class="hs-fsel" data-filter="' + id + '">' + opts.map(function (o) {
        return '<option value="' + (o[0] == null ? '' : o[0]) + '"' +
          (String(cur == null ? '' : cur) === String(o[0] == null ? '' : o[0]) ? ' selected' : '') +
          '>' + esc(o[1]) + '</option>';
      }).join('') + '</select>';
    }
    return '<span class="hs-lay"><button type="button" class="hs-chip" id="hs-filtbtn"' +
      (n ? ' aria-pressed="true"' : '') + ' aria-expanded="false">' + esc(S('filtBtn')) +
      (n ? ' (' + n + ')' : '') + ' &#9662;</button>' +
      '<div class="hs-laymenu hs-filtmenu" id="hs-filtmenu" hidden>' +
        '<label>' + esc(S('filtBudget')) + sel('maxPrice', priceOpts, state.maxPrice) + '</label>' +
        '<label>' + esc(S('filtYield')) + sel('minYield', yieldOpts, state.minYield) + '</label>' +
        '<label>' + esc(S('filtMrt')) + sel('maxMrt', mrtOpts, state.maxMrt) + '</label>' +
        (n ? '<button type="button" class="hs-chip" data-filter="clear" ' +
             'style="width:100%;margin-top:6px">' + esc(S('filtClear')) + '</button>' : '') +
      '</div></span>';
  }

  // ══════════════════════════════════════════════════ SECTIONS ══════════

  // Buildings with BOTH a sale and a lease on file, before any of this site's
  // own filters. It is the waterfall's own step 0 and it is 27.8%, against the
  // 6.22% the hero used to quote as if it were the same thing.
  function bothRecordsPct() {
    var wf = D.coverage_waterfall, s = wf && wf.steps && wf.steps[0];
    if (!s || !s.from) return D.headline.coverage_pct;
    return s.to / s.from * 100;
  }

  function socialStepPp() {
    var s = ((D.coverage_waterfall || {}).steps || []).filter(function (x) { return x.key === 'social'; })[0];
    return s ? s.lost_pp : 0;
  }
  function asmDefault(key) {
    var a = (D.assumptions || []).filter(function (x) { return x.key === key; })[0];
    return a ? a.default : '?';
  }

  function secHero() {
    var h = D.headline;
    var ci = D.bootstrap && D.bootstrap.overall;
    if (ci && (ci.lo == null || ci.hi == null)) ci = null;
    return '<header class="hs-hero hs-wrap">' +
      '<h1>' + esc(Sf('heroH', Math.round(100 / h.coverage_pct))) + '</h1>' +
      '<p class="lede hs-prose">' + esc(S('heroP')) + '</p>' +
      '<div class="hs-vs" style="margin-top:var(--sp7)">' +
        '<div class="hs-vs-item"><div class="hs-vs-v" style="color:var(--accent)" id="hs-fig">' +
          h.coverage_pct.toFixed(1) + '%</div>' +
          '<div class="hs-vs-l" id="hs-figcap">' + esc(S('heroCov')) + '</div></div>' +
        // The ceiling sits NEXT TO the coverage figure, not in a footnote.
        // The two of them bound every possible version of this analysis, and
        // that pair is the one-line summary of the whole page.
        '<div class="hs-vs-item"><div class="hs-vs-v">' +
          h.coverage_ceiling_pct.toFixed(1) + '%</div>' +
          '<div class="hs-vs-l">' + esc(S('heroCeil')) + '</div></div>' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + h.yield.toFixed(2) + '%</div>' +
          '<div class="hs-vs-l">' + esc(Sf('heroYield', n0(h.buildings))) +
          (ci ? '<br><span class="hs-sub2">' + esc(Sf('ci95', ci.lo.toFixed(2), ci.hi.toFixed(2))) +
            '</span>' : '') + '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v" id="hs-netfig">' +
          (h.net == null ? '--' : h.net.toFixed(2) + '%') + '</div>' +
          '<div class="hs-vs-l">' + esc(S('heroNet')) + '</div></div>' +
      '</div>' +
      // Three thresholds, in order: both records at all (27.8%), both within
      // the 4-quarter window (24.0%), both and this site's quality bar (6.22%).
      // The page used to quote the first and second two paragraphs apart with
      // nothing saying how they differ.
      '<p class="hs-plain">' + esc(Sf('heroBound', bothRecordsPct().toFixed(1),
          h.coverage_ceiling_pct.toFixed(1), h.coverage_pct.toFixed(2))) + '</p>' +
      // Four cold readers each found this fact on the LAST screen, under a
      // 9,805-row table, and three said it changed how they read every rent
      // number above it. It belongs here, with the reconciliation they asked
      // for: 82% is a share of LEASES, -10.4pp a share of BUILDINGS -- a
      // building survives on one market lease, and social leases pile into a
      // few 包租代管 towers.
      (D.rent_bias && D.rent_bias.social_share_pct != null
        ? '<p class="hs-plain">' + esc(Sf('heroSocial',
            D.rent_bias.social_share_pct.toFixed(1),
            Math.abs(D.rent_bias.gap_pct).toFixed(0),
            socialStepPp().toFixed(1))) + '</p>' : '') +
      // And the schedule behind 1.84%, which three of four said they could not
      // verify without. Read from the assumptions the sliders use.
      '<p class="hs-fig-n hs-prose">' + esc(Sf(MODE === 'advanced' ? 'heroCostsA' : 'heroCosts',
          h.net == null ? '--' : h.net.toFixed(2), asmDefault('tax'),
          asmDefault('mgmt'), asmDefault('vacancy'), asmDefault('repairs'))) + '</p>' +
      '<div class="hs-stats">' +
        stat(n0(h.universe_buildings), S('sUniverse')) +
        stat(n0(h.buildings), S('sBuildings')) +
        stat(n0(h.pairs), S('sPairs')) +
        stat(D.meta.n_seasons, S('sSeasons')) +
      '</div>' +
    '</header>';
  }
  function stat(v, l) {
    return '<div class="hs-stat"><span class="hs-stat-v">' + esc(v) +
      '</span><span class="hs-stat-l">' + esc(l) + '</span></div>';
  }

  // ── yield vs distance to the nearest MRT station ───────────────────────
  //
  // The payload already carries `mrt` (metres, straight line) and `mrts`
  // (station name) on 8,798 of 9,805 buildings, so this is computed here
  // rather than in the build: it is a read of data already shipped.
  //
  // The chart is deliberately TWO panels. Nationally the spread runs 2.10% to
  // 2.91%, which looks like a strong distance effect and mostly is not — a
  // building 3 km from a station is usually in a different, cheaper city.
  // Inside 臺北市 the same gradient survives at about a quarter of the size.
  // Showing only the national panel would be the flattering version of this
  // finding, and this page does not get to publish flattering versions.
  var MRT_MAX_M = 15000;
  var MRT_BINS = [[0, 250], [250, 500], [500, 750], [750, 1000],
                  [1000, 1500], [1500, 2500], [2500, MRT_MAX_M]];
  var MRT_LAB = ['<250', '250–500', '500–750', '750–1k', '1k–1.5k', '1.5k–2.5k', '>2.5k'];

  function mrtBins(rows, seedBase, field) {
    field = field || 'mrt';
    return MRT_BINS.map(function (b, i) {
      var g = rows.filter(function (r) {
        return r[field] != null && r[field] >= b[0] && r[field] < b[1];
      });
      // The page's own sample floor. A bin under it shows nothing rather than
      // a number nobody should read.
      if (g.length < 25) return null;
      var ys = g.map(function (r) { return r.y; });
      var ci = bootCI(ys, (seedBase || 0) * 101 + i + 1);
      return {
        lab: MRT_LAB[i], n: g.length,
        y: medianOf(ys), lo: ci && ci.lo, hi: ci && ci.hi,
        p: medianOf(g.map(function (r) { return r.p; })),
        // Rent per ping per year. The section's mechanism claim is about how
        // price and rent move APART with distance, so both have to be carried
        // or the claim is unfalsifiable on the page that makes it.
        r: medianOf(g.map(function (r) { return r.r; }))
      };
    }).filter(Boolean);
  }

  function mrtSummary(rows) {
    var body = rows.map(function (r) {
      var s = r[1];
      if (!s) return '';
      return '<tr><td>' + esc(r[0]) + '</td>' +
        '<td class="num">' + (s.spread >= 0 ? '+' : '') + s.spread.toFixed(2) + ' pp</td>' +
        '<td>' + esc(S(s.separate ? 'mrtSep' : 'mrtOv')) + '</td></tr>';
    }).join('');
    return '<div class="hs-scroll" style="margin-top:var(--sp4)"><table style="font-size:13.5px" aria-label="' + esc(S('mrtSumSpread')) + '"><thead><tr>' +
      '<th style="cursor:default"></th>' +
      '<th style="cursor:default;text-align:right">' + esc(S('mrtSumSpread')) + '</th>' +
      '<th style="cursor:default">' + esc(S('mrtSumCI')) + '</th></tr></thead><tbody>' +
      body + '</tbody></table></div>';
  }

  function mrtPanel(title, bins, maxY) {
    if (!bins.length) return '';
    var W = chartW(480), barH = 22, gap = 12, padL = 92, padR = 118;
    var H = 26 + bins.length * (barH + gap);
    var sc = (W - padL - padR) / maxY;
    var body = bins.map(function (b, i) {
      var y = 20 + i * (barH + gap);
      var w = Math.max(2, b.y * sc);
      // The interval is drawn ON the bar, in the same ink. A bar without one
      // reads as a measurement; most of these bins overlap their neighbours and
      // the reader has to be able to see that without doing arithmetic.
      // The interval STRADDLES the end of the bar: its lower half lies on the
      // hatched fill and its upper half on the page. A single ink works on one
      // ground and vanishes on the other -- drawn in --bg it was invisible past
      // the bar end, which is where the upper bound always is. So each stroke is
      // laid twice: a thick --bg halo to clear the hatch, then a thin --text
      // line on top that reads against both.
      var whisk = '';
      if (b.lo != null && b.hi != null) {
        var x0 = padL + b.lo * sc, x1 = padL + b.hi * sc, cy = y + barH / 2;
        var segs = [[x0, cy, x1, cy], [x0, cy - 5, x0, cy + 5], [x1, cy - 5, x1, cy + 5]];
        whisk = segs.map(function (s) {
          return '<line x1="' + s[0].toFixed(1) + '" y1="' + s[1] + '" x2="' + s[2].toFixed(1) +
            '" y2="' + s[3] + '" stroke="var(--bg)" stroke-width="4.5" stroke-linecap="butt"/>';
        }).join('') + segs.map(function (s) {
          return '<line x1="' + s[0].toFixed(1) + '" y1="' + s[1] + '" x2="' + s[2].toFixed(1) +
            '" y2="' + s[3] + '" stroke="var(--text)" stroke-width="1.6" stroke-linecap="butt"/>';
        }).join('');
      }
      return txt(padL - 10, y + barH / 2 + 4, b.lab, 'hs-glab', 'end') +
        rect(padL, y, w, barH, 'url(#hxbar)',
             ' stroke="var(--text)" stroke-width="1.1"') + whisk +
        txt(padL + w + 9, y + barH / 2 + 1, b.y.toFixed(2) + '%', 'hs-vlab', 'start') +
        txt(padL + w + 9, y + barH / 2 + 14, 'n=' + n0(b.n) +
            (b.lo != null ? '  ' + b.lo.toFixed(2) + '–' + b.hi.toFixed(2) : ''),
            'hs-glab', 'start',
            ' style="fill:var(--subtle);font-size:10px"');
    }).join('');
    return '<div><div class="hs-fig-t">' + esc(title) + '</div>' +
      '<div class="hs-scroll">' + svg(W, H, body, 'hs-axis', title + ' — ' + S('mrtBin') + ' · ' + S('mrtYield')) + '</div></div>';
  }

  // The matched set against the whole stock, by age band. The existing
  // dumbbell compares matched to UNMATCHED-but-sold, which is the registry's
  // own denominator. This is the house-tax roll: every residential unit in
  // Taiwan, by age. Two distributions side by side, never divided -- the
  // stock is in 宅 and the site counts 棟.
  function ageVsStock() {
    var a = D.moi.stock_by_age;
    if (!a || !a.rows || !a.rows.length) return '';
    var W = chartW(560), H = 24 + a.rows.length * 22 + 10, padL = 108, barW = Math.max(120, W - padL - 120), gap = 12;
    var mx = 0;
    a.rows.forEach(function (r) { mx = Math.max(mx, r.stock_pct, r.ours_pct); });
    var body = a.rows.map(function (r, i) {
      var y = 20 + i * 22;
      var ws = r.stock_pct / mx * barW, wo = r.ours_pct / mx * barW;
      return txt(padL - 8, y + 13, r.band.replace('（含）', ''), 'hs-glab', 'end') +
        // stock: hatched (the world). ours: outline (the slice). Same grammar
        // as the rent-bias and cost charts.
        rect(padL, y + 2, Math.max(1, ws), 8, 'url(#hxbar)', ' stroke="var(--text)" stroke-width=".8"') +
        rect(padL, y + 11, Math.max(1, wo), 8, 'none', ' stroke="var(--text)" stroke-width="1.2"') +
        txt(padL + Math.max(ws, wo) + 6, y + 13, r.stock_pct.toFixed(0) + '% / ' + r.ours_pct.toFixed(0) + '%',
            'hs-glab', 'start', ' style="fill:var(--subtle);font-size:10.5px"');
    }).join('');
    var young = a.rows.filter(function (r) { return /^1~5|^5~10|^1（含）/.test(r.band); });
    var old = a.rows.filter(function (r) { return /^40|^50/.test(r.band); });
    function sum(rows, k) { return rows.reduce(function (s, r) { return s + r[k]; }, 0); }
    return fig(Sf('ageStockT', a.stock_mean_age.toFixed(1), a.ours_median_age.toFixed(1)),
               S('ageStockS'), svg(W, H, body)) +
      '<p class="hs-plain">' + esc(Sf('ageStockP',
          sum(old, 'stock_pct').toFixed(0), sum(old, 'ours_pct').toFixed(0),
          sum(young, 'stock_pct').toFixed(0), sum(young, 'ours_pct').toFixed(0))) + '</p>';
  }

  function secMRT() {
    // The station layer is the TAIPEI network -- 131 stations. Every building
    // still gets a "distance to the nearest station", so a Kaohsiung flat came
    // out at a median 274,843 m and a Taichung one at 112,217 m. Those are not
    // distances to anything; they are the distance to Taipei. 73% of the old
    // ">2.5 km" bin was buildings like that, which made the national panel a
    // map of which city you are in wearing a distance label.
    //
    // MRT_MAX_M keeps only buildings the layer can actually speak about. What
    // is left is 北北桃, and the question becomes answerable: inside the
    // network's real coverage, does distance matter?
    var rows = (D.buildings || []).filter(function (b) {
      return b.mrt != null && b.y != null && b.mrt < MRT_MAX_M;
    });
    // No MRT geometry in the payload (or nobody near a station) -> no section.
    // A chart of an empty set is worse than no chart.
    if (rows.length < 200) return '';
    var all = mrtBins(rows, 1);
    // Same buildings, heavy rail only. The gap between these two panels is the
    // whole result: it is not a finding about transit, it is a finding about
    // what you decide a station is.
    var heavy = mrtBins(rows.filter(function (b) { return b.mrth != null; }), 3, 'mrth');
    // 臺北市 was the wrong control. It is dense enough that only 4 of its
    // buildings sit beyond 2.5 km, so its "null" was an empty far group, not an
    // absent effect -- and this page published that null as a retraction.
    // 新北市 is the one county carrying both a real near group and a real far
    // group, so it is the honest within-city test.
    var ctl = 'f';
    var tpe = mrtBins(rows.filter(function (b) { return b.c === ctl; }), 2);
    // 高雄市 is the first genuinely independent replication the station layer
    // makes possible -- a separate metro, a separate city, built after the
    // finding was claimed. It is the test that matters.
    var rep2 = mrtBins(rows.filter(function (b) { return b.c === 'e'; }), 4);
    function sep(bins) {
      if (bins.length < 2) return null;
      var a = bins[0], z = bins[bins.length - 1];
      if (a.hi == null || z.lo == null) return null;
      return { spread: z.y - a.y, separate: a.hi < z.lo, n0: a.n, n1: z.n };
    }
    var sAll = sep(all), sHeavy = sep(heavy), sCtl = sep(tpe), sRep = sep(rep2);
    // The definitional test has to run where the effect is claimed -- 新北市 --
    // not nationally, or the numbers quoted do not belong to the story told
    // about them (淡海輕軌 is a New Taipei line).
    var ctlRows = rows.filter(function (b) { return b.c === ctl; });
    var sCtlAll = sep(mrtBins(ctlRows, 5));
    var sCtlHeavy = sep(mrtBins(ctlRows.filter(function (b) { return b.mrth != null; }),
                                6, 'mrth'));
    if (all.length < 3) return '';
    var maxY = 0;
    all.concat(heavy, tpe, rep2).forEach(function (b) {
      maxY = Math.max(maxY, b.hi != null ? b.hi : b.y);
    });

    var near = all[0], far = all[all.length - 1];
    var share = (rows.length / (D.buildings || []).length * 100).toFixed(0) + '%';

    // Does the gradient survive holding CITY constant? The section used to
    // assert that it does. With intervals attached it does not: inside 臺北市
    // the nearest and furthest bands overlap. And the MECHANISM reverses --
    // nationally price falls faster than rent, inside Taipei they fall at the
    // same rate, so the national divergence is a between-city artefact.
    function drop(bins, key) {
      if (bins.length < 2 || !bins[0][key] || !bins[bins.length - 1][key]) return null;
      return (bins[bins.length - 1][key] / bins[0][key] - 1) * 100;
    }
    var natP = drop(all, 'p'), natR = drop(all, 'r');
    var tpeNear = tpe[0], tpeFar = tpe[tpe.length - 1];
    var tpeOverlap = tpe.length >= 2 && tpeNear.hi != null && tpeFar.lo != null
      && tpeNear.hi >= tpeFar.lo;
    var covered = {};
    rows.forEach(function (b) { covered[b.c] = (covered[b.c] || 0) + 1; });
    var tpeP = drop(tpe, 'p'), tpeR = drop(tpe, 'r');

    return sec('mrtEy', null, 0,
      // Holds only if it survives both station definitions AND replicates in
      // an independent city. Anything less and the heading says so.
      '<h2>' + esc(S((sHeavy && sHeavy.separate && sAll && sAll.separate &&
                      sRep && sRep.separate) ? 'mrtH' : 'mrtH2')) + '</h2>' +
      '<p class="hs-prose lede">' +
        esc(Sf('mrtP', near.y.toFixed(2) + '%', far.y.toFixed(2) + '%',
               natP == null ? '?' : Math.abs(natP).toFixed(1),
               natR == null ? '?' : Math.abs(natR).toFixed(1))) + '</p>' +
      '<div class="hs-fig"><div class="hs-fig-s">' + esc(S('mrtBin')) + ' &middot; ' +
        esc(S('mrtYield')) + '</div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:28px">' +
          mrtPanel(S('mrtAll'), all, maxY) +
          (MODE === 'advanced'
            ? mrtPanel(S('mrtHeavyL'), heavy, maxY) +
              mrtPanel(S('mrtCtl'), tpe, maxY) +
              mrtPanel(S('mrtRepL'), rep2, maxY)
            : mrtSummary([[S('mrtAll'), sAll], [S('mrtHeavyL'), sHeavy],
                          [S('mrtCtl'), sCtlAll], [S('mrtRepL'), sRep]])) +
        '</div></div>' +
      '<p class="hs-plain">' + esc(S('mrtVerdict')) + '</p>' +
      (sCtlHeavy && sCtlAll ? '<p class="hs-prose">' + esc(Sf('mrtDefn',
          countyName(ctl),
          (sCtlHeavy.spread >= 0 ? '+' : '') + sCtlHeavy.spread.toFixed(3),
          S(sCtlHeavy.separate ? 'mrtSep' : 'mrtOv'),
          (sCtlAll.spread >= 0 ? '+' : '') + sCtlAll.spread.toFixed(3),
          S(sCtlAll.separate ? 'mrtSep' : 'mrtOv'))) + '</p>' : '') +
      (sRep ? '<p class="hs-prose">' + esc(Sf('mrtRep',
          rep2[0].y.toFixed(2), rep2[rep2.length - 1].y.toFixed(2),
          (sRep.spread >= 0 ? '+' : '') + sRep.spread.toFixed(3),
          S(sRep.separate ? 'mrtSep' : 'mrtOv'))) + '</p>' : '') +
      (MODE === 'advanced' ? '<p class="hs-prose hs-fig-n">' + esc(S('mrtHist')) + '</p>' : '') +
      // Identification, stated out loud. This finding and the floor finding are
      // NOT peers and the page should not present them as such.
      (MODE === 'advanced' ? '<p class="hs-prose hs-fig-n">' + esc(S('identBetween')) + '</p>' : '') +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('mrtN',
          n0(((D.map || {}).base || {}).stations ? D.map.base.stations.length : 0),
          n0(rows.length), share)) + '</p>');
  }

  // 金拍 auction results. ADVANCED on purpose: it is a side channel with real
  // caveats -- a different auction system from 法拍, much smaller, and carrying
  // no floor area at all -- and advanced mode is where this page keeps its
  // methodological side-findings. The one number that belongs to the main
  // argument, how little of the channel the registry can see, is stated first.

  // The other half of the founding hypothesis. secDead keeps the 'alive'
  // rung; this settles what the data can and cannot say, and publishes the
  // half it cannot as unanswerable rather than leaving it open.
  function secWalkup() {
    var w = D.walkup_resolution;
    if (!w || !w.coverage || !w.precision || !w.verdict) return '';
    var cov = w.coverage, pr = w.precision, cs = w.common_support || {}, me = w.mechanism || {};
    var rep = {}; (w.representativeness || []).forEach(function (r) { rep[r.type] = r; });
    var A = w.types.a, Bt = w.types.b;
    var rw = rep[A], rt = rep[Bt];
    if (!rw || !rt) return '';
    var ctl = {}; (w.controls || []).forEach(function (c) { ctl[c.family] = c; });
    function g(f) { var c = ctl[f]; return c && c.median_gap != null ? c.median_gap.toFixed(2) : '--'; }
    function f2(v) { return v == null ? '--' : v.toFixed(2); }

    // two verdict chips, each naming its own question
    var vlab = { resolved_walkups_higher: 'wuVResolved', resolved_towers_higher: 'wuVResolved',
                 unanswerable_selection: 'wuVUnansSel', unanswerable_precision: 'wuVUnansPre',
                 inconclusive: 'wuVInc' }[w.verdict] || 'wuVInc';
    var mlab = w.mechanism_verdict === 'attributable' ? 'wuVResolved' : 'wuVMechUnans';
    var chips = '<div class="hs-vs" style="max-width:720px">' +
      '<div class="hs-vs-item"><div class="hs-vs-v" style="font-size:clamp(18px,2.6vw,24px)">' +
        esc(S(vlab)) + '</div><div class="hs-vs-l">' + esc(S('wuVLevel')) + '</div></div>' +
      '<div class="hs-vs-item muted"><div class="hs-vs-v" style="font-size:clamp(18px,2.6vw,24px)">' +
        esc(S(me.fee_verdict === 'falsified' ? 'wuVMechKill' : 'wuVInc')) + ' · ' + esc(S(mlab)) +
        '</div><div class="hs-vs-l">' + esc(S('wuVMech')) + '</div></div></div>';

    // controls: horizontal bars labelled at ONE end, so chartW applies
    var fams = (w.controls || []).filter(function (c) { return c.median_gap != null || c.cells === 0; });
    var W = chartW(560), padL = 176, padR = 78, RH = 26, padT = 10;
    var H = padT + fams.length * RH + 26;
    var mx = Math.max.apply(null, fams.map(function (c) { return Math.abs(c.median_gap || 0); }).concat([0.5]));
    var x0 = padL, PW = W - padL - padR;
    var body = line(x0, padT, x0, H - 24, 'var(--text)', 1) +
      txt(x0, H - 8, '0', 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:10px"');
    fams.forEach(function (c, i) {
      var y = padT + i * RH, v = c.median_gap || 0, wdt = Math.abs(v) / mx * PW;
      var lab = S('wuF_' + c.family) === 'wuF_' + c.family ? c.family : S('wuF_' + c.family);
      body += txt(padL - 10, y + 16, lab, 'hs-glab', 'end',
                  c.binding ? '' : ' style="fill:var(--subtle)"') +
        (c.cells === 0
          ? (function () {
              var nc = Sf('wuNoCell', n0(c.min_n));
              // anchored to the right wall when it would not fit from the bar
              var fits = nc.length * (LANG === 'zh' ? 11 : 6.2) <= W - (x0 + 6) - 4;
              return fits
                ? txt(x0 + 6, y + 16, nc, 'hs-glab', 'start',
                      ' style="fill:var(--subtle);font-size:10px"')
                : txt(W - 4, y + 16, nc, 'hs-glab', 'end',
                      ' style="fill:var(--subtle);font-size:10px"');
            }())
          : rect(v >= 0 ? x0 : x0 - wdt, y + 4, Math.max(1, wdt), 15,
                 c.binding ? 'url(#hxbar)' : 'url(#hxbarL)',
                 ' stroke="var(--text)" stroke-width=".7"' + (c.binding ? '' : ' opacity=".55"')) +
            txt(x0 + wdt + 8, y + 16, (v >= 0 ? '+' : '') + v.toFixed(2) + 'pp', 'hs-vlab', 'start',
                ' style="font-size:10.5px"') +
            txt(x0 + wdt + 8, y + 25, n0(c.cells) + ' cells · ' + c.cover_pct.toFixed(0) + '%',
                'hs-glab', 'start', ' style="fill:var(--subtle);font-size:9px"'));
    });
    var figCtl = fig(S('wuFCtlT'), S('wuFCtlS'), svg(W, H, body, 'hs-axis'));

    // age overlap: two histograms, many columns -> natural width, pans
    var figAge = '';
    if (D.buildings) {
      var bins = [], BW = 5, MAXA = 70;
      for (var i = 0; i < MAXA / BW; i++) bins.push({ lo: i * BW, w: 0, t: 0 });
      D.buildings.forEach(function (bb) {
        if (bb.b == null) return;
        var a = 115 - bb.b; if (a < 0 || a >= MAXA) return;
        var k = Math.floor(a / BW);
        if (bb.t === A) bins[k].w++; else if (bb.t === Bt) bins[k].t++;
      });
      var tw = bins.reduce(function (s, x) { return s + x.w; }, 0) || 1;
      var tt = bins.reduce(function (s, x) { return s + x.t; }, 0) || 1;
      var W2 = 620, H2 = 190, pl2 = 42, pb2 = 32, pt2 = 14;
      var cw = (W2 - pl2 - 14) / bins.length;
      var mxs = Math.max.apply(null, bins.map(function (x) { return Math.max(x.w / tw, x.t / tt); }));
      var b2 = '';
      var ow = cs.overlap_window || {};
      if (ow.lo != null) {
        var ox = pl2 + (ow.lo / BW) * cw, oxw = ((ow.hi - ow.lo) / BW) * cw;
        b2 += rect(ox, pt2, oxw, H2 - pt2 - pb2, 'var(--subtle)', ' opacity=".16"');
      }
      bins.forEach(function (x, i) {
        var xx = pl2 + i * cw;
        var hw = x.w / tw / mxs * (H2 - pt2 - pb2), ht = x.t / tt / mxs * (H2 - pt2 - pb2);
        b2 += rect(xx + 1, H2 - pb2 - hw, cw / 2 - 1.5, hw, 'url(#hxbar)', ' stroke="var(--text)" stroke-width=".6"') +
              rect(xx + cw / 2 + 0.5, H2 - pb2 - ht, cw / 2 - 1.5, ht, 'none', ' stroke="var(--text)" stroke-width="1"');
        if (i % 2 === 0) b2 += txt(xx + cw / 2, H2 - 12, x.lo, 'hs-axis', 'middle',
                                   ' style="fill:var(--muted);font-size:9.5px"');
      });
      figAge = fig(S('wuFAgeT'), S('wuFAgeS'), svg(W2, H2, b2, 'hs-axis'),
        '<div class="hs-legend"><b><i class="hs-swatch hx-hi"></i>' + esc(countyName ? A : A) +
        '</b><b><i class="hs-swatch"></i>' + esc(Bt) + '</b></div>');
    }

    // the mechanism 2x2
    var mtbl = '';
    if ((me.cells || []).length === 2) {
      mtbl = '<div class="hs-scroll"><table aria-label="' + esc(S('wuThMgr')) + '" style="font-size:13.5px">' +
        '<thead><tr><th>' + esc(S('wuThMgr')) + '</th><th class="num">' + esc(S('wuThNW')) + '</th>' +
        '<th class="num">' + esc(S('wuThNT')) + '</th><th class="num">' + esc(S('wuThGap')) + '</th>' +
        '<th class="num">95% CI</th><th class="num">' + esc(S('wuThNet')) + '</th></tr></thead><tbody>' +
        me.cells.map(function (c) {
          return '<tr><td>' + esc(S(c.has_mgr ? 'wuYes' : 'wuNo')) + '</td><td class="num">' + n0(c.n_walkup) +
            '</td><td class="num">' + n0(c.n_tower) + '</td><td class="num">' + (c.gross_gap >= 0 ? '+' : '') +
            c.gross_gap.toFixed(3) + 'pp</td><td class="num">' + (c.lo == null ? '--' : f2(c.lo) + '–' + f2(c.hi)) +
            '</td><td class="num">' + (c.net_gap >= 0 ? '+' : '') + c.net_gap.toFixed(3) + 'pp</td></tr>';
        }).join('') + '</tbody></table></div>';
    }

    var dh = D.dead_hypothesis || {};
    return sec('wuEy', null, 1,
      '<h2>' + esc(Sf('wuH', pr.gross_gap.toFixed(2))) + '</h2>' +
      '<p class="hs-prose lede">' + esc(S('wuP1')) + '</p>' + chips +
      '<p class="hs-prose">' + esc(Sf('wuCov', n0(cov.matched_bldg), n0(cov.site_bldg),
        cov.matched_share_of_site_pct.toFixed(2), n0(cov.universe_bldg), cov.match_rate_pct.toFixed(2),
        n0(cov.sale_rows), n0(cov.pairs), n0(cov.pairs_per_bldg_median), n0(cov.tower_pairs_per_bldg_median),
        n0(cov.stock_4_5f_dwellings), cov.stock_period)) + '</p>' +
      '<h3>' + esc(S('wuRepH')) + '</h3>' +
      '<p class="hs-prose">' + esc(Sf('wuRep', n0(rw.medians.built.m), n0(rw.medians.built.u),
        rw.medians.area_ping.m.toFixed(1), rw.medians.area_ping.u.toFixed(1),
        rw.medians.area_ping.diff_pct.toFixed(1), n0(rw.medians.ppp.m), n0(rw.medians.ppp.u),
        rt.medians.area_ping.m.toFixed(1), rt.medians.area_ping.u.toFixed(1),
        rt.medians.area_ping.diff_pct.toFixed(1))) + '</p>' +
      '<p class="hs-prose">' + esc(Sf('wuPrec', pr.gross_gap.toFixed(3), f2(pr.mdd_95),
        pr.ratio_obs_to_mdd, f2(pr.lo), f2(pr.hi))) + '</p>' +
      '<p class="hs-prose">' + esc(Sf('wuCtl', g('price_decile'), g('county_district'), g('county'),
        g('age_band'), g('size_band'), g('has_mgr'), n0(cs.joint_min_n), n0(cs.joint_cells_at_min_n))) + '</p>' +
      figCtl +
      '<p class="hs-prose">' + esc(Sf('wuSupp', n0(cs.walkup_age.median), n0(cs.walkup_age.p5), n0(cs.walkup_age.p95),
        n0(cs.tower_age.median), n0(cs.tower_age.p5), n0(cs.tower_age.p95),
        cs.towers_over_40y_pct.toFixed(1), cs.walkups_under_20y_pct.toFixed(1),
        n0((cs.overlap_window || {}).lo), n0((cs.overlap_window || {}).hi),
        f2((cs.overlap_window || {}).gap), f2((cs.overlap_window || {}).lo_ci), f2((cs.overlap_window || {}).hi_ci),
        n0((cs.overlap_window || {}).n_walkup), n0((cs.overlap_window || {}).n_tower))) + '</p>' +
      figAge +
      '<p class="hs-prose">' + esc(Sf('wuMech', me.p_mgr_walkup_pct.toFixed(1), me.p_mgr_tower_pct.toFixed(1),
        n0((me.cells[0] || {}).n_walkup), n0((me.cells[0] || {}).n_tower),
        f2((me.cells[0] || {}).gross_gap), f2((me.cells[0] || {}).lo), f2((me.cells[0] || {}).hi))) + '</p>' +
      mtbl +
      '<p class="hs-prose">' + esc(Sf('wuUnans', Math.abs(rw.max_abs_diff_pct).toFixed(1),
        Math.abs(rt.max_abs_diff_pct).toFixed(1))) + '</p>' +
      '<p class="hs-prose">' + esc(Sf('wuNeed', cov.match_rate_pct.toFixed(2))) + '</p>' +
      (dh.gross_gap != null ? '<p class="hs-fig-n hs-prose">' + esc(Sf('wuAccrete',
        dh.gross_gap.toFixed(3), dh.net_gap.toFixed(3))) + '</p>' : '') +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('wuRule', n0(w.constants.min_n), w.constants.mdd_z,
        w.constants.sel_tol_pct.toFixed(0), (w.constants.sign_share * 100).toFixed(0),
        n0(w.constants.joint_min_cells), n0(w.constants.joint_min_n),
        Math.max(Math.abs(rw.max_abs_diff_pct), Math.abs(rt.max_abs_diff_pct)).toFixed(1),
        n0(cs.joint_cells_at_min_n))) + '</p>');
  }

  // Every figure in this sentence lives in auction.by_round, and the 金拍 feed
  // is fetched live, so the window -- and all nine numbers -- move on every
  // rebuild. They used to be typed into the string.
  function aucRoundText(a) {
    var br = a.by_round || {};
    var r1 = br['1'], r3 = br['3'], r4 = br['4'];
    if (!r1 || !r3 || !r4 || !a.items) return '';
    var tail = r3.n + r4.n;
    var over = [r3.median_over_pct, r4.median_over_pct]
      .filter(function (x) { return x != null; });
    var med = over.length ? over.reduce(function (x, y) { return x + y; }, 0) / over.length : 0;
    return Sf('aucRound', r1.above_reserve_pct.toFixed(1), n0(r1.n),
              r3.above_reserve_pct.toFixed(1), n0(r3.n),
              r4.above_reserve_pct.toFixed(1), n0(r4.n),
              n0(tail), (tail / a.items * 100).toFixed(1), med.toFixed(1));
  }

  function secAuction() {
    var a = D.auction;
    if (!a || !a.items || a.in_registry_pct == null) return '';

    var rounds = Object.keys(a.by_round || {}).map(Number).sort(function (x, y) {
      return x - y;
    });
    var bars = rounds.map(function (r) {
      var v = a.by_round[r];
      var w = Math.max(2, v.above_reserve_pct / 100 * 300);
      return '<div class="hs-wf-row">' +
        '<span class="hs-wf-l">' + esc(Sf('aucRoundL', r)) + '</span>' +
        '<span class="hs-wf-bar"><i class="hs-wf-fill solid" style="left:0;width:' +
          (v.above_reserve_pct).toFixed(1) + '%"></i></span>' +
        '<span class="hs-wf-v">' + v.above_reserve_pct.toFixed(0) + '%' +
          '<span class="hs-sub2"> n=' + n0(v.n) + '</span></span></div>';
    }).join('');

    return sec('aucEy', 'aucH', 1,
      '<p class="hs-prose lede">' +
        // in_registry_pct is a share of LOTS (hit.mean() over the row-level
        // frame), and it was printed against a count of BUILDINGS -- the same
        // unit-mixing that made the honesty ladder read backwards. Both units
        // are now named.
        esc(Sf('aucReg', n0(a.addr_keyed), n0(a.buildings),
               a.in_registry_pct.toFixed(1))) + '</p>' +
      '<p class="hs-prose">' + esc(S('aucP')) + '</p>' +
      '<div class="hs-vs hs-mort">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' +
          a.in_registry_pct.toFixed(1) + '%</div>' +
          '<div class="hs-vs-l">' + esc(S('aucInReg')) + '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' +
          a.above_reserve_pct.toFixed(1) + '%</div>' +
          '<div class="hs-vs-l">' + esc(S('aucAbove')) + '</div></div>' +
      '</div>' +
      '<p class="hs-prose">' +
        esc(Sf('aucRes', n0(a.items),
               n0(Math.round(a.items * a.above_reserve_pct / 100)))) + '</p>' +
      (bars ? '<div class="hs-fig"><div class="hs-fig-s">' + esc(S('aucAbove')) +
        '</div><div class="hs-wf">' + bars + '</div></div>' +
        '<p class="hs-plain">' + esc(aucRoundText(a)) + '</p>' : '') +
      '<p class="hs-fig-n hs-prose">' +
        esc(Sf('aucNote', a.date_min || '?', a.date_max || '?',
               n0(a.sessions_cached || 0))) + '</p>');
  }

  // 預售屋. Simple mode, because the lead is the page-s central argument seen at
  // its largest: a whole segment the headline cannot see even in principle.
  //
  // The chart is the correction, and it has to be shown WITH the naive number
  // rather than instead of it. A reader who sees only "+30%" has been told
  // something false; a reader who sees only "+4%" has been told the conclusion
  // without the evidence. The bars falling from left to right ARE the argument.
  function secPresale() {
    var p = D.presale;
    if (!p || !p.curve || p.curve.length < 2) return '';

    // Two bars per row. The presale gap, and beneath it the SAME shift run
    // between two completed groups where no delivery wait exists. Drawing the
    // placebo anywhere other than directly under the thing it falsifies would
    // let a reader take the top row as a finding, which it is not.
    var W = chartW(560), H = 44 + p.curve.length * 46, padL = 96, padR = 110;
    var mx = 0;
    p.curve.forEach(function (c) {
      mx = Math.max(mx, Math.abs(c.gap_pct), Math.abs(c.placebo_pct || 0));
    });
    // These values CHANGE SIGN: +5.4 at lag 0 down to -7.5 at the far end, and
    // the sentence above the figure is precisely "the gap shrinks all the way to
    // negative". Drawing |v| from a single origin made -7.5% the longest bar on
    // the canvas, pointing the same way as +5.4%, so the chart said the opposite
    // of its own caption. Zero sits in the middle and negatives run left, which
    // is what secWalkup already does.
    var half = (W - padL - padR) / 2;
    var zero = padL + half;
    var scale = function (v) { return Math.max(2, Math.abs(v) / mx * half); };
    var barX = function (v, w) { return v >= 0 ? zero : zero - w; };
    var bars = p.curve.map(function (c, i) {
      var y = 18 + i * 46;
      var w = scale(c.gap_pct), bx = barX(c.gap_pct, w);
      var row = txt(padL - 10, y + 12, c.lag_q === 0 ? S('preNow')
                      : Sf('preYr', c.lag_years.toFixed(1)), 'hs-glab', 'end') +
        rect(bx, y, w, 17, 'url(#hxbar)',
             ' stroke="var(--text)" stroke-width="1.1"') +
        txt(c.gap_pct >= 0 ? bx + w + 9 : bx - 9, y + 13, (c.gap_pct >= 0 ? '+' : '') +
            c.gap_pct.toFixed(1) + '%', 'hs-vlab', c.gap_pct >= 0 ? 'start' : 'end') +
        // The interval is the honest width of each rung. 261 cells at the first
        // rung are only 71 district x type clusters, and 55 cells at the last
        // are 30 — the cell count flatters the evidence and the CI corrects it.
        (c.ci_lo == null ? '' :
          txt(c.gap_pct >= 0 ? bx + w + 9 : bx - 9, y + 25,
              '[' + c.ci_lo.toFixed(1) + ', ' + c.ci_hi.toFixed(1) + ']',
              'hs-glab', c.gap_pct >= 0 ? 'start' : 'end',
              ' style="fill:var(--subtle);font-size:10px"'));
      if (c.placebo_pct != null) {
        var w2 = scale(c.placebo_pct), bx2 = barX(c.placebo_pct, w2);
        row += rect(bx2, y + 21, w2, 12, 'none',
                    ' stroke="var(--text)" stroke-width="1.1"') +
          txt(c.placebo_pct >= 0 ? bx2 + w2 + 9 : bx2 - 9, y + 31,
              (c.placebo_pct > 0 ? '+' : '') +
              c.placebo_pct.toFixed(1) + '%', 'hs-glab',
              c.placebo_pct >= 0 ? 'start' : 'end',
              ' style="fill:var(--muted);font-size:10.5px"');
      }
      return row;
    }).join('');

    var _preH = Sf('preH', (p.naive_gap_pct == null ? '--' : p.naive_gap_pct.toFixed(1)));
    return sec('preEy', null, 0,
      '<h2>' + esc(_preH) + '</h2>' +
      '<p class="hs-prose lede">' +
        esc(Sf('preLead', n0(p.dwellings))) + '</p>' +
      '<div class="hs-vs hs-mort">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + n0(p.dwellings) + '</div>' +
          '<div class="hs-vs-l">' + esc(S('preUnits')) + '</div></div>' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + n0(p.projects) + '</div>' +
          '<div class="hs-vs-l">' + esc(S('preProj')) + '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">0</div>' +
          '<div class="hs-vs-l">' + esc(S('preNoYield')) + '</div></div>' +
      '</div>' +
      '<p class="hs-prose">' + esc(Sf('preGap', p.naive_gap_pct.toFixed(1))) + '</p>' +
      '<p class="hs-prose">' +
        esc(Sf('preLag', Math.abs(p.far_gap_pct).toFixed(1))) + '</p>' +
      '<div class="hs-fig"><div class="hs-fig-s">' + esc(S('preX')) + '</div>' +
        '<div class="hs-legend"><b><i class="hs-swatch hx-hi"></i>' +
          esc(S('preEy')) + '</b><b><i class="hs-swatch"></i>' +
          esc(S('prePlacL')) + '</b></div>' +
        '<div class="hs-scroll">' +
          svg(W, H, line(zero, 8, zero, H - 14, 'var(--text)', 1) +
                    txt(zero, H - 4, '0', 'hs-axis', 'middle',
                        ' style="fill:var(--muted);font-size:10px"') + bars,
              'hs-axis', _preH) + '</div></div>' +
      '<p class="hs-plain">' +
        esc(Sf('prePlac',
               Math.abs(p.curve[p.curve.length - 1].placebo_pct == null ? 0
                 : p.curve[p.curve.length - 1].placebo_pct).toFixed(1),
               p.curve[0].gap_pct.toFixed(1), p.curve[0].ci_lo.toFixed(1), p.curve[0].ci_hi.toFixed(1))) + '</p>' +
      // the five-lag ratio detail and the correction of an early figure move
      // behind the advanced toggle; four cold readers lost their place here
      (MODE === 'advanced' ? '<p class="hs-prose hs-fig-n">' + esc(Sf('prePlacAdv',
          p.curve.map(function (c) {
            var pl = c.placebo_pct == null ? 0 : c.placebo_pct;
            return ((1 + c.gap_pct / 100) / (1 + pl / 100) * 100 - 100).toFixed(1);
          }).join('、'), p.curve[0].gap_pct.toFixed(1),
          (p.residual_pct == null ? 0 : p.residual_pct).toFixed(1))) + '</p>' : '') +
      (p.reach_pct != null
        ? '<p class="hs-prose">' + esc(Sf('preReach', n0(p.reach_dwellings),
            p.reach_pct.toFixed(1), n0(p.reach_districts), n0(p.total_districts),
            n0(p.reach_cells), p.naive_gap_pct.toFixed(1))) + '</p>'
        : '') +
      '<p class="hs-fig-n hs-prose">' + esc(S('preLim')) + '</p>');
  }

  // Counts, not yields. The one section not aggregated at building level:
  // a transaction count is not a yield. Two figures that share no axis, so
  // nothing can be read as a fraction of the other.
  function secVolume() {
    var v = D.volume;
    if (!v || !v.series || !v.quarters) return '';
    var c = (state.volCounty && v.series[state.volCounty]) ? state.volCounty : 'all';
    var s = v.series[c], Q = v.quarters, n = Q.length;
    var o = v.official && v.official.series && v.official.series[c];
    var sm = v.summary || {};
    var censored = {}; (v.censored || []).forEach(function (q) { censored[q] = true; });
    var qi = {}; Q.forEach(function (q, i) { qi[q] = i; });

    // chips: 全國 + the six big counties
    var chips = '<div class="hs-controls">' +
      '<button class="hs-chip" data-vol="" aria-pressed="' + (c === 'all') + '">' + esc(S('volAll')) + '</button>' +
      v.counties.filter(function (k) { return k !== 'all'; }).map(function (k) {
        return '<button class="hs-chip" data-vol="' + esc(k) + '" aria-pressed="' + (c === k) + '">' +
          esc(countyName(k)) + '</button>';
      }).join('') + '</div>';

    // Figure A: three bands, one per file, each on its own scale
    var bands = [['existing', 'volSerE', 'url(#hxbar)', ' stroke="var(--text)" stroke-width=".8"'],
                 ['presale', 'volSerP', 'url(#hxbarL)', ' stroke="var(--text)" stroke-width=".8"'],
                 ['leases', 'volSerL', 'none', ' stroke="var(--text)" stroke-width="1.1"']]
      .filter(function (b) { return s[b[0]]; });
    // Natural width, not chartW(): eleven columns each carrying a value label
    // cannot shrink to a phone. Column charts scroll inside .hs-scroll (the
    // district chart's rule); chartW is for horizontal bars labelled at the end.
    var W = 640, padL = 118, padR = 14, BH = 92, padT = 22, padB = 30;
    var H = padT + bands.length * BH + padB;
    var PW = W - padL - padR, colW = PW / n, barW = Math.max(6, colW * 0.62);
    var colX = function (i) { return padL + i * colW; };
    var body = '';
    bands.forEach(function (b, bi) {
      var vals = s[b[0]], mx = Math.max.apply(null, vals.concat([1]));
      var y0 = padT + bi * BH, base = y0 + BH - 22;
      body += rowLabel(padL - 10, y0 + 12, S(b[1]), padL) +
        txt(padL - 10, y0 + 26, 'max ' + n0(mx), 'hs-glab', 'end',
            ' style="fill:var(--subtle);font-size:10px"') +
        line(padL, base + 0.5, W - padR, base + 0.5, 'var(--grid)', 1);
      vals.forEach(function (val, i) {
        var hgt = Math.max(1, val / mx * (BH - 36));
        var x = colX(i) + (colW - barW) / 2, y = base - hgt;
        var cens = censored[Q[i]];
        body += rect(x, y, barW, hgt, cens ? 'var(--subtle)' : b[2],
                     cens ? ' class="hs-vol-cens"' : b[3]) +
          txt(x + barW / 2, y - 3, n0(val), 'hs-vlab', 'middle',
              ' style="font-size:10.5px' + (cens ? ';fill:var(--muted)' : '') + '"');
      });
    });
    // x labels under the bottom band; the censored column tagged
    Q.forEach(function (q, i) {
      body += txt(colX(i) + colW / 2, H - 12, q, 'hs-axis', 'middle',
                  ' style="fill:var(--muted);font-size:10.5px"');
      if (censored[q]) body += txt(colX(i) + colW / 2, padT - 8, S('volCensL'), 'hs-glab', 'middle',
                                   ' style="fill:var(--muted);font-size:10px"');
    });
    // the three events, dashed, spanning every band; numbered at the top
    (v.events || []).forEach(function (e, k) {
      if (qi[e.q] == null) return;
      var x = colX(qi[e.q]) + e.frac * colW;
      body += line(x, padT - 2, x, H - padB + 4, 'var(--text)', 1, ' class="hs-vol-ev"') +
        txt(x + (k === 0 ? -4 : 4), padT - 8, ['①', '②', '③'][k], 'hs-vol-evn',
            k === 0 ? 'end' : 'start');
    });
    var figA = fig(S('volFigA'), S('volFigASub'), svg(W, H, body, 'hs-axis'),
      '<div class="hs-fig-n">' + [S('volEv1'), S('volEv2'), S('volEv3')].map(esc).join(' &middot; ') + '</div>' +
      '<div class="hs-fig-n">' + esc(S('volXCon')) + '</div>');

    // Figure B: the official 棟 series, its own card, its own axis
    var figB = '';
    if (o) {
      var W2 = 640, pl2 = 64, H2 = 200, pb2 = 30, pt2 = 26;
      var mx2 = Math.max.apply(null, o.concat([1]));
      var PW2 = W2 - pl2 - padR, cw2 = PW2 / n, bw2 = Math.max(6, cw2 * 0.62);
      var b2 = '';
      ticks(0, mx2, 4).forEach(function (t) {
        var y = H2 - pb2 - t / mx2 * (H2 - pt2 - pb2);
        b2 += line(pl2, y + 0.5, W2 - padR, y + 0.5, 'var(--grid)', 1) +
          txt(pl2 - 6, y + 4, n0(t), 'hs-axis', 'end', ' style="fill:var(--muted);font-size:10px"');
      });
      o.forEach(function (val, i) {
        var hgt = val / mx2 * (H2 - pt2 - pb2), x = pl2 + i * cw2 + (cw2 - bw2) / 2, y = H2 - pb2 - hgt;
        b2 += rect(x, y, bw2, hgt, 'var(--text)', ' opacity=".85"') +
          txt(x + bw2 / 2, y - 3, n0(val), 'hs-vlab', 'middle', ' style="font-size:10.5px"') +
          txt(x + bw2 / 2, H2 - 12, Q[i], 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:10.5px"');
      });
      figB = fig(S('volFigB'), Sf('volFigBSub', v.official.period_last,
                   n0(v.official.series.all[v.official.series.all.length - 1])),
                 svg(W2, H2, b2, 'hs-axis'),
                 '<div class="hs-fig-n">' + esc(S('volXReg')) + '</div>');
    }

    var arr = v.arrival || {}, ae = arr.existing || {}, ap = arr.presale || {};
    var capVals = Object.keys(v.captured_pct || {}).map(function (q) { return v.captured_pct[q]; })
      .filter(function (x) { return x != null; });
    var table = '';
    if (MODE === 'advanced') {
      table = '<h3>' + esc(S('volTblH')) + '</h3><div class="hs-scroll"><table aria-label="' + esc(S('volTblH')) + '">' +
        '<thead><tr><th>' + esc(S('volTblQ')) + '</th>' +
        bands.map(function (b) { return '<th class="num">' + esc(S(b[1])) + '</th>'; }).join('') +
        (o ? '<th class="num">' + esc(S('volTblO')) + '</th>' : '') + '</tr></thead><tbody>' +
        Q.map(function (q, i) {
          return '<tr><td>' + esc(q) + (censored[q] ? ' ' + esc(S('volCensL')) : '') + '</td>' +
            bands.map(function (b) { return '<td class="num">' + n0(s[b[0]][i]) + '</td>'; }).join('') +
            (o ? '<td class="num">' + n0(o[i]) + '</td>' : '') + '</tr>';
        }).join('') + '</tbody></table></div>' +
        (capVals.length ? '<p class="hs-fig-n">' + esc(Sf('volCaptured',
            Math.min.apply(null, capVals).toFixed(1), Math.max.apply(null, capVals).toFixed(1))) + '</p>' : '');
    }

    return sec('volEy', 'volH', 0,
      '<p class="hs-prose lede">' + esc(Sf('volLead', Q[0], Q[n - 1],
        sm.peak_q, n0(sm.peak_existing), sm.after_q, n0(sm.after_existing),
        (sm.existing_change_pct == null ? '--' : sm.existing_change_pct.toFixed(1)),
        n0(sm.presale_from), n0(sm.presale_to),
        (sm.presale_change_pct == null ? '--' : sm.presale_change_pct.toFixed(1)),
        sm.presale_to_q,
        n0(sm.leases_from), n0(sm.leases_to), sm.leases_to_q)) + '</p>' +
      chips + figA +
      '<p class="hs-prose">' + esc(Sf('volHorizon',
        (((ae['0'] || 0) + (ae['1'] || 0)) * 100).toFixed(0),
        ((ae['2'] || 0) * 100).toFixed(1),
        ((ae['3+'] || 0) * 100).toFixed(1))) + '</p>' +
      (v.censored && v.censored.length
        ? '<p class="hs-prose">' + esc(Sf('volCensor', v.censored[0],
            ((ae['0'] || 0) * 100).toFixed(0), ((ap['0'] || 0) * 100).toFixed(0))) + '</p>' : '') +
      '<p class="hs-prose">' + esc(Sf('volPresaleOrigin', n0(v.kinds.presale_origin),
        v.presale_origin_pct.toFixed(1))) + '</p>' +
      '<p class="hs-prose">' + esc(S('volEvents')) + '</p>' +
      figB +
      (o ? '<p class="hs-prose">' + esc(S('volNoRatio')) + '</p>' +
           (qi['113Q3'] != null && qi['114Q1'] != null
             ? '<p class="hs-fig-n hs-prose">' + esc(Sf('volLag', n0(o[qi['113Q3']]), n0(o[qi['113Q4']]), n0(o[qi['114Q1']]))) + '</p>'
             : '')
         : '') +
      table +
      '<p class="hs-fig-n hs-prose">' + esc(S('volLim')) + '</p>');
  }

  function secCoverage() {
    var cov = D.coverage, age = D.age;
    var tower = cov.filter(function (c) { return c.type === '住宅大樓'; })[0];
    var walk = cov.filter(function (c) { return c.type === '公寓'; })[0];

    var W = chartW(560), H = 168, padL = 90, barH = 34, gap = 18;
    var maxR = Math.max.apply(null, cov.map(function (c) { return c.match_rate; }));
    var bars = cov.map(function (c, i) {
      var y = 14 + i * (barH + gap);
      var w = c.match_rate / maxR * (W - padL - 92);
      return txt(padL - 12, y + barH / 2 + 4, typeLabel(c.type), 'hs-glab', 'end') +
        rect(padL, y, w, barH, typeHatch(c.type),
             ' stroke="var(--text)" stroke-width="1.1"') +
        txt(padL + w + 10, y + barH / 2 + 5, c.match_rate.toFixed(1) + '%', 'hs-vlab', 'start') +
        txt(padL + w + 10, y + barH / 2 + 19, n0(c.matched) + ' / ' + n0(c.all_buildings),
            'hs-glab', 'start', ' style="fill:var(--subtle);font-size:10.5px"');
    }).join('');

    // Three columns when the MOI stock is in the payload: the house-tax
    // roll (every residential unit, by floor band mapped onto the site's three
    // types), buildings with a sale, and buildings the site can price. The
    // first column is the denominator a reader means by "Taiwan's housing";
    // the second is the one the registry allows. Both were needed -- the page
    // used to show only the second and the skew read as smaller than it is.
    var stockShare = null;
    if (D.moi && D.moi.stock_by_floor && D.moi.stock_by_floor.by_type) {
      stockShare = {};
      D.moi.stock_by_floor.by_type.forEach(function (r) {
        stockShare[r.type] = r.share_of_inside_pct;
      });
    }
    var three = !!stockShare;
    var W2 = chartW(560), H2 = 190, top = 30, hgt = 122;
    var bw = three ? Math.round(W2 * 0.17) : Math.round(W2 * 0.2);
    var slot = three ? W2 / 3 : W2 / 2;
    var x0 = three ? Math.round(slot * 0.5 - bw / 2) : null;
    var x1 = three ? Math.round(slot * 1.5 - bw / 2) : Math.round(slot * 0.5 - bw / 2);
    var x2 = three ? Math.round(slot * 2.5 - bw / 2) : Math.round(slot * 1.5 - bw / 2);
    function stack(x, label, field) {
      var acc = 0;
      return cov.map(function (c) {
        var v = field === 'stock' ? (stockShare[c.type] || 0) : c[field];
        var hh = v / 100 * hgt, y = top + acc / 100 * hgt;
        acc += v;
        return rect(x, y + 1, bw, hh - 2, typeHatch(c.type),
                    ' stroke="var(--text)" stroke-width=".8"') +
          (hh > 20 ? txt(x + bw / 2, y + hh / 2 + 4, v.toFixed(0) + '%', 'hs-vlab', 'middle',
            ' style="fill:var(--text);font-size:12px;paint-order:stroke;'
            + 'stroke:var(--paper);stroke-width:3px;stroke-linejoin:round"') : '');
      }).join('') +
        // A centred column label overflows the canvas on the outer columns at
        // phone width -- 「住宅存量（4 層以上）」 ran 10 units past the left edge
        // and the SVG clips. Anchor the outer ones to the wall instead.
        (function () {
          var c = x + bw / 2, half = label.length * 6;   // ~6 units a glyph at 12px
          if (c - half < 2) return txt(2, top - 10, label, 'hs-glab', 'start', ' style="font-weight:600"');
          if (c + half > W2 - 2) return txt(W2 - 2, top - 10, label, 'hs-glab', 'end', ' style="font-weight:600"');
          return txt(c, top - 10, label, 'hs-glab', 'middle', ' style="font-weight:600"');
        }());
    }

    var yrs = Math.round(Math.abs(age.matched_built - age.unmatched_built));
    var W3 = chartW(560), H3 = 118, ax = 60, aw = W3 - ax - 60;
    var alo = Math.min(age.matched_built, age.unmatched_built) - 10;
    var ahi = Math.max(age.matched_built, age.unmatched_built) + 10;
    var AX = function (v) { return ax + (v - alo) / (ahi - alo) * aw; };
    var ay = 60;
    var aGrid = ticks(Math.ceil(alo / 5) * 5, Math.floor(ahi / 5) * 5, 5).map(function (t) {
      return line(AX(t), 26, AX(t), H3 - 26, 'var(--grid)', 1) +
        txt(AX(t), H3 - 10, Math.round(t), 'hs-axis', 'middle',
            ' style="fill:var(--muted);font-size:11px"');
    }).join('');
    var dumb = aGrid +
      line(AX(age.unmatched_built), ay, AX(age.matched_built), ay, 'var(--dim)', 3, ' stroke-linecap="round"') +
      '<circle cx="' + AX(age.unmatched_built) + '" cy="' + ay + '" r="8" fill="var(--dim)" stroke="var(--surface)" stroke-width="2"/>' +
      '<circle cx="' + AX(age.matched_built) + '" cy="' + ay + '" r="8" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>' +
      txt(AX(age.unmatched_built) - 14, ay + 5, S('ageUn') + ' ' + age.unmatched_built, 'hs-vlab', 'end') +
      txt(AX(age.matched_built) + 14, ay + 5, S('ageMatched') + ' ' + age.matched_built, 'hs-vlab', 'start',
          ' style="fill:var(--accent)"');

    // Waterfall: whose fault is each lost building. Shown in BOTH modes --
    // it is the honesty qualifier on the hero number, not a method detail.
    var wf = D.coverage_waterfall, WW = chartW(640), wrowH = 30;
    // Label column 250px on desktop; on a phone that plus the 78px value
    // column left 7px for the longest bar. Proportional, with the long labels
    // allowed to wrap onto two lines when the column is narrow.
    var wfPadL = Math.min(250, Math.round(WW * (WW < 480 ? 0.5 : 0.44))), wfPadR = 74;
    var wfSvg = '';
    (function () {
      var maxpp = Math.max.apply(null, wf.steps.map(function (x) { return x.lost_pp; }));
      wf.steps.forEach(function (st, i) {
        var y = 8 + i * wrowH;
        var w = st.lost_pp / maxpp * (WW - wfPadL - wfPadR);
        wfSvg += rowLabel(wfPadL - 6, y + 15, LANG === 'zh' ? st.zh : st.en, wfPadL,
                     WW < 480 ? ' style="font-size:10px"' : '') +
          rect(wfPadL, y + 4, w, 18,
               st.whose === 'law' ? 'url(#hxbarL)' : 'url(#hxbar)',
               ' stroke="var(--text)" stroke-width=".8"') +
          txt(wfPadL + w + 8, y + 17, '-' + st.lost_pp.toFixed(1) + 'pp', 'hs-vlab', 'start');
      });
    })();
    var wfLegend = '<div class="hs-legend">' +
      '<b><i class="hs-swatch hx-lo"></i>' + esc(S('wfLaw')) + '</b>' +
      '<b><i class="hs-swatch hx-hi"></i>' + esc(S('wfOurs')) + '</b></div>';

    var ppd = age.ppp_diff_pct;
    var W4 = chartW(560), H4 = 96, px = W4 < 480 ? 96 : 210, pw4 = W4 - px - 110;
    var pmax = Math.max(age.matched_ppp, age.unmatched_ppp);
    var priceSvg = [[S('ageUn'), age.unmatched_ppp, 'var(--dim)'],
                    [S('ageMatched'), age.matched_ppp, 'var(--accent)']]
      .map(function (r, i) {
        var y = 14 + i * 38, w = r[1] / pmax * pw4;
        return txt(px - 12, y + 17, r[0], 'hs-glab', 'end') +
          rect(px, y + 3, w, 22, r[2], '') +
          txt(px + w + 10, y + 19, money(r[1]), 'hs-vlab', 'start');
      }).join('');

    return sec('covEy', 'covH', 0,
      // The two share figures used to be typed in as 49% and 14%. They were
      // measured across Taipei and New Taipei and never updated when the scope
      // went national, where they are 36.4% and 7.8%. Derived now.
      '<p class="hs-prose lede">' + esc(Sf('covP', tower.match_rate.toFixed(1) + '%',
          walk.match_rate.toFixed(1) + '%', walk.share_all.toFixed(1),
          walk.share_matched.toFixed(1))) + '</p>' +
      fig(Sf('wfH', (100 - D.headline.coverage_pct).toFixed(0)), null,
          svg(WW, 8 + wf.steps.length * wrowH + 6, wfSvg), wfLegend) +
      '<p class="hs-prose">' + esc(Sf('wfP', wf.law_pp,
          (wf.steps || []).filter(function (s) { return s.whose === 'ours'; }).length,
          wf.ours_pp)) + ' ' +
        esc(Sf('wfCeil', wf.ceiling_pct)) + '</p>' +
      fig(S('covRate'), S('covRateS'), svg(W, H, bars)) +
      fig(S('covMix'), three ? S('covMixS3') : S('covMixS'), svg(W2, H2,
          (three ? stack(x0, S('covStock'), 'stock') : '') +
          stack(x1, S('covAll'), 'share_all') +
          stack(x2, S('covMatched'), 'share_matched')), legend(TYPES)) +
      (three ? '<p class="hs-plain">' + esc(Sf('covStockP',
          stockShare['住宅大樓'].toFixed(0), tower.share_matched.toFixed(0),
          stockShare['公寓'].toFixed(0), walk.share_matched.toFixed(0),
          D.moi.stock_by_floor.outside_pct.toFixed(0))) + '</p>' +
        '<p class="hs-fig-n hs-prose">' + esc(Sf('covStockN', D.moi.stock_by_floor.period)) + '</p>' : '') +
      (D.moi && D.moi.stock_by_age ? ageVsStock() : '') +
      fig(Sf('ageT', yrs), S('ageS'), svg(W3, H3, dumb)) +
      fig(Sf('priceT', ppd == null ? '--' : ppd.toFixed(0)), S('priceS'),
          svg(W4, H4, priceSvg)) +
      '<div class="hs-callout hs-prose"><p>' + esc(S('covPunch')) + '</p></div>');
  }


  // ── the map ───────────────────────────────────────────────────────────
  // A real map, drawn from government geometry, with no tile layer and no
  // library. Pan and zoom move the SVG viewBox rather than re-rendering: with
  // 41 district polygons (4,831 vertices), a 2,000-cell density grid and 2,541
  // points, rebuilding the markup on every drag frame would stutter, and the
  // browser transforms it for free.
  //
  // Everything is drawn in TWD97 / TM2 metres inside a scale(1,-1) group, so
  // the coordinates ARE the projection and north is up. Consequences: strokes
  // need vector-effect="non-scaling-stroke", and anything sized in screen terms
  // (dot radius, label size) is rescaled by fitView() whenever the zoom changes.
  var _mapV = null;      // current viewBox {x, y, w, h} in metre-space
  var _mapHome = null;
  // The density grid is OFF by default now that the polygon is a choropleth. Two
  // area fills on the same map compete for the same channel, and the grid was
  // winning: 400 m cells of grey checkerboard over the value the map is for. It
  // is still one click away in the layer menu, and the coverage argument it
  // makes has its own section above the map.
  var _layers = { roads: true, mrt: true, water: true, dens: false, labels: true,
                  excl: true };

  // Shape carries 建物型態, colour carries yield. Two variables, two channels --
  // and because type is no longer colour-only, the map still works for a reader
  // who cannot separate the hues.
  function symbolPath(type, x, y, r) {
    if (type === '公寓') {                       // walk-up: circle
      return '<circle cx="' + x + '" cy="' + y + '" r="' + r.toFixed(0) + '"';
    }
    if (type === '華廈') {                       // mid-rise: diamond
      var d = r * 1.25;
      return '<path data-cx="' + x + '" data-cy="' + y + '" d="M' + x + ' ' + (y - d) +
        'L' + (x + d) + ' ' + y + 'L' + x + ' ' + (y + d) + 'L' + (x - d) + ' ' + y + 'Z"';
    }
    var h = r * 1.05;                            // tower: square
    return '<rect data-cx="' + x + '" data-cy="' + y + '" x="' + (x - h) + '" y="' + (y - h) +
      '" width="' + (h * 2) + '" height="' + (h * 2) + '"';
  }

  // The viewBox is fitted to the DRAWING SURFACE's aspect ratio, not the data's.
  // The data bounds are 1.10 wide-to-tall against a 1.375 surface, and
  // preserveAspectRatio="meet" silently letterboxed the difference -- while
  // toWorld() maps clientX linearly across the whole element, so every
  // wheel-zoom anchor and every click was displaced horizontally by the
  // letterbox. Matching the aspect makes `meet` a no-op and toWorld() exact.
  var MAP_W = 880, MAP_H = 640;

  // The drawing surface is `height: auto`, so its shape IS the viewBox's shape.
  // On a phone a 1.375 landscape box is 341x248 css px -- a third of the screen,
  // and far too small for 33 badges. A portrait box gives back 60% of the height.
  function mapAR() {
    if ((window.innerWidth || 900) <= 700) return 0.86;
    // The canvas follows the DATA's shape, not a fixed landscape box.
    //
    // Taiwan is a portrait country: the buildings span 169 x 305 km, an aspect
    // of 0.55, and forcing that into 880/640 = 1.375 gave a 457 km-wide viewport
    // for 169 km of data. Two thirds of the width was sea, and the country was
    // drawn small in the middle of it.
    //
    // The floor is 1.15, measured rather than chosen. ONE canvas has to serve
    // all three levels, and a county's own shape is not portrait, so pushing the
    // aspect all the way to the data's 0.55 fixes the national view and wrecks
    // the county ones: 高雄 goes from 0 overlapping labels to 6. Swept over
    // 1.375 / 1.15 / 1.0 / 0.9 / 0.78, the 1.15 row wins on BOTH counts at once
    // -- the country fills 44% of the width instead of 37%, and total county
    // overlaps fall from 4 to 3. tests/test_housing_map_layout.py holds the line.
    var b = D.map && D.map.bounds;
    if (!b) return MAP_W / MAP_H;
    var ar = (b[2] - b[0]) / (b[3] - b[1]);
    return Math.max(1.15, Math.min(MAP_W / MAP_H, ar));
  }

  function fitBox(x0, y0, x1, y1, pad) {
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    var w = Math.max(1, (x1 - x0) * (1 + pad));
    var h = Math.max(1, (y1 - y0) * (1 + pad));
    var R = mapAR();
    if (w / h < R) w = h * R; else h = w / R;
    // y is negated because everything is drawn inside scale(1,-1) so that north
    // is up and the coordinates stay the raw TM2 projection.
    return { x: cx - w / 2, y: -cy - h / 2, w: w, h: h };
  }

  var _mapHomeAR = null;
  function mapHome() {
    // Rotating a phone, or dragging a desktop window across the 700 px
    // breakpoint, changes the target shape -- a cached home box would then be
    // the wrong shape for the surface it is drawn on.
    if (_mapHome && _mapHomeAR === mapAR()) return _mapHome;
    var b = D.map && D.map.bounds;
    if (!b) return null;
    _mapHomeAR = mapAR();
    // 9% padding, not 6%: an edge district's badge carries a name UNDER it, and
    // 烏來區 sits hard against the southern bound.
    _mapHome = fitBox(b[0], b[1], b[2], b[3], 0.09);
    return _mapHome;
  }

  // Yield is the dominant variable, so it gets a real sequential ramp. It used
  // to be one hue light -> dark; it is now HATCH DENSITY, because the page has
  // no hue left to spend. A blue->purple->green rainbow was suggested and
  // declined long before that, for the reason that still applies: a rainbow is
  // not perceptually ordered, so the reader cannot tell which end means "more"
  // without re-reading the key. Density can only be read one way.
  //
  // Six steps, and density is PITCH plus NIB — never opacity. A grey made with
  // opacity is a flat fill, and a flat fill is the one thing this drawing does
  // not contain; every tone here is countable lines. Coverage (nib/pitch) runs
  // 10% -> 64% monotonically, which is what makes the ramp ordinal.
  //
  // ONE angle throughout. Cross-hatching would give more separation at the top
  // but it cannot be tiled seamlessly at a 30deg offset inside a square tile,
  // and a second angle on the map would collide with the rule that an angle
  // change means a real boundary. Cross-hatch stays reserved for STATES.
  var YSTEPS = 6;

  // [pitch, nib] in CSS PIXELS. The map cannot use pixels directly: its user
  // unit is a METRE (see commit()), so these are multiplied by mpp on every
  // zoom, exactly as stroke widths already are. Apparent pitch therefore stays
  // constant on screen from 22 counties down to a single building.
  var HATCH = [[9.0, 0.9], [6.4, 1.0], [5.0, 1.2], [4.4, 1.5], [4.0, 1.9], [3.6, 2.3]];

  // The six tiles. Sizes here are placeholders: sizeHatch() sets them in metres
  // on every zoom. The stroke is var(--text), not a hex, so a theme flip
  // repaints the whole choropleth with no re-render -- the same property the
  // --y1..--y6 tokens used to provide.
  //
  // rotate(-28) draws lines 62deg off horizontal. The negative is not a typo:
  // these tiles are referenced by paths inside <g transform="scale(1,-1)">, and
  // that flip mirrors every angle. Written as +28 the map's hatch would run
  // against the CSS hatch in the legend and in the rest of the page.
  function hatchDefs() {
    var out = '<defs>';
    for (var i = 0; i < HATCH.length; i++) {
      var p = HATCH[i][0];
      out += '<pattern id="hx' + (i + 1) + '" patternUnits="userSpaceOnUse" ' +
        'width="' + p + '" height="' + p + '" patternTransform="rotate(-28)">' +
        '<line x1="0" y1="0" x2="0" y2="' + p + '" stroke="var(--text)" ' +
        'stroke-width="' + HATCH[i][1] + '"/></pattern>';
    }
    return out + '</defs>';
  }

  // A 9-unit tile on this map is a NINE-METRE tile: at national zoom that is
  // 0.02 px and moires into mud; at building zoom it is 18 px and reads as
  // stripes rather than tone. So the tile and its nib are set in metres from
  // mpp, exactly as commit() already does for every stroke width on the map.
  //
  // Guarded on mpp because commit() also runs on pan, and a drag would
  // otherwise cost 18 attribute writes per frame for a scale that has not
  // changed. 2% is below the threshold where a pitch shift is visible.
  var _hatchMpp = null;
  function sizeHatch(mpp) {
    if (_hatchMpp !== null && Math.abs(mpp / _hatchMpp - 1) < 0.02) return;
    _hatchMpp = mpp;
    for (var i = 0; i < HATCH.length; i++) {
      var pat = document.getElementById('hx' + (i + 1));
      if (!pat) continue;
      var p = (HATCH[i][0] * mpp).toFixed(4);
      pat.setAttribute('width', p);
      pat.setAttribute('height', p);
      var ln = pat.firstElementChild;
      if (ln) {
        ln.setAttribute('y2', p);
        ln.setAttribute('stroke-width', (HATCH[i][1] * mpp).toFixed(4));
      }
    }
  }

  // The ramp's DOMAIN comes from the payload, not from here. It used to be the
  // literal (v - 1.6) / 2.0 -- the Taipei/New Taipei spread -- which clamps every
  // building above 3.6% to the top step. Central and southern yields run higher,
  // so a hard-coded domain would paint whole cities one flat colour and call it
  // a ramp. The fallback is the old pair, so a payload without it still renders.
  // The ramp follows what is being coloured.
  //
  // Buildings spread 1.55-5.00%, county medians only 2.06-3.68%. Painting
  // counties on the building ramp put 7 of 14 on the same step and used 4 of the
  // 6 colours, so the national view -- the only one most readers ever see -- was
  // effectively monochrome. A median is a different quantity from a building and
  // needs its own domain.
  function rampDomain(level) {
    var M = D.map || {};
    var r = (level === 0 ? M.ramp_county : level === 1 ? M.ramp_district : null) || M.ramp;
    return (r && r.length === 2 && r[1] > r[0]) ? r : [1.6, 3.6];
  }

  function yieldFillAt(v, level) {
    var R = rampDomain(level);
    var t = Math.max(0, Math.min(0.999, (v - R[0]) / (R[1] - R[0])));
    return 'url(#hx' + (Math.floor(t * YSTEPS) + 1) + ')';
  }

  function yieldFill(v) {
    var R = rampDomain();
    var t = Math.max(0, Math.min(0.999, (v - R[0]) / (R[1] - R[0])));
    return 'url(#hx' + (Math.floor(t * YSTEPS) + 1) + ')';
  }

  // Grouping is by ADMINISTRATIVE DISTRICT, not by a screen-space grid.
  //
  // A grid bucket is an artefact of the current zoom: it has no name, no
  // boundary and no meaning, so a "23" floating over a road told the reader
  // nothing they could act on, and the same building joined a different bucket
  // every time the scale changed. A district is a real place people search in,
  // price in and argue about, and it is the unit the rest of this page already
  // reports in -- so the badge now reads "大安區 / 206 buildings / median
  // 2.31%", and clicking it frames that district and opens every building in it.
  //
  // Cached on the filter key: the groups only change when the filtered set does.
  var _dgCache = null, _dgKey = null;
  function districtGroups() {
    var B = filtered();
    if (_dgKey === _fKey && _dgCache) return _dgCache;
    // A district's COUNT and MEDIAN come from every building in it. Only the
    // dots need a coordinate.
    //
    // This used to `continue` on a missing coordinate, so a district was painted
    // by the buildings we happened to be able to place. That was already a small
    // lie — 石門區 and 萬里區 have matched buildings and were drawn as empty,
    // because their three buildings are among the eight whose 門牌 never joined —
    // and nationally it becomes a large one: address-point files exist for five
    // counties, so every district in the other seventeen would have been painted
    // "no data" while its buildings sat in the table underneath.
    var map = {}, out = [];
    for (var i = 0; i < B.length; i++) {
      var b = B[i];
      var k = b.c + '|' + b.d, g = map[k];
      if (!g) {
        g = map[k] = { key: k, district: b.d, county: b.c, x: 0, y: 0, np: 0,
                       ys: [], items: [], placed: [],
                       bb: [Infinity, Infinity, -Infinity, -Infinity] };
        out.push(g);
      }
      g.ys.push(b.y); g.items.push(b);
      if (b.mx == null) continue;
      g.placed.push(b);
      g.np++; g.x += b.mx; g.y += b.my;
      if (b.mx < g.bb[0]) g.bb[0] = b.mx;
      if (b.my < g.bb[1]) g.bb[1] = b.my;
      if (b.mx > g.bb[2]) g.bb[2] = b.mx;
      if (b.my > g.bb[3]) g.bb[3] = b.my;
    }
    for (var j = 0; j < out.length; j++) {
      var o = out[j], n = o.items.length;
      o.n = n;
      // Anchor an unplaceable district on its polygon instead, so it still gets
      // a mark and a name rather than silently vanishing off the map.
      if (o.np) { o.x /= o.np; o.y /= o.np; }
      else {
        var pb2 = polyBBox(o.key);
        if (pb2) {
          o.x = (pb2[0] + pb2[2]) / 2; o.y = (pb2[1] + pb2[3]) / 2;
          o.bb = pb2.slice();
        } else {
          var c = (D.map.labels || {})[o.key];
          if (c) { o.x = c[0]; o.y = c[1]; o.bb = [c[0], c[1], c[0], c[1]]; }
        }
      }
      o.ys.sort(function (p, q) { return p - q; });
      o.med = n % 2 ? o.ys[(n - 1) / 2] : (o.ys[n / 2 - 1] + o.ys[n / 2]) / 2;
    }
    out = out.filter(function (g) { return isFinite(g.x) && isFinite(g.y); });
    _dgKey = _fKey; _dgCache = out;
    return out;
  }

  // Extent of the drawn POLYGONS, per district and per county.
  //
  // The fallback for a group with no placeable building used to be its centroid
  // as a zero-size box, and districtView()'s 900 m floor then turned that into a
  // 1 km view: clicking 臺中市 — 475 buildings, no address-point file yet — flew
  // to a 200 m scale bar in the middle of nowhere. A county still has an outline
  // even when it has no dots, and the outline is the right thing to fit.
  //
  // Computed once over the shipped rings and cached; a county key is the union
  // of its districts.
  var _pbb = null;
  function polyBBox(key) {
    if (!_pbb) {
      _pbb = {};
      var ds = (D.map && D.map.districts) || [];
      for (var i = 0; i < ds.length; i++) {
        var d = ds[i], dk = d.county + '|' + d.district;
        for (var r = 0; r < d.rings.length; r++) {
          var ring = d.rings[r];
          for (var q = 0; q < ring.length; q++) {
            var x = ring[q][0], y = ring[q][1];
            var a = _pbb[dk] || (_pbb[dk] = [Infinity, Infinity, -Infinity, -Infinity]);
            var b = _pbb[d.county] || (_pbb[d.county] = [Infinity, Infinity, -Infinity, -Infinity]);
            if (x < a[0]) a[0] = x; if (y < a[1]) a[1] = y;
            if (x > a[2]) a[2] = x; if (y > a[3]) a[3] = y;
            if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y;
            if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y;
          }
        }
      }
    }
    return _pbb[key] || null;
  }

  // EVERY district of a county, whether or not anything matched in it.
  //
  // districtGroups() is built from buildings, so a district with no matched pair
  // simply did not exist as a mark: opening 臺南市 showed 20 of its 37 districts,
  // 高雄市 24 of 38, 屏東縣 6 of 33 — 166 of 365 nationally. A reader clicking a
  // city is asking to see that city, not the 45% of it we happen to have pairs
  // for, and a district with nothing in it is a real answer.
  //
  // The polygon set is the authority for WHICH districts exist; districtGroups()
  // supplies the numbers where there are any.
  var _adCache = null, _adKey = null;
  function allDistricts(county) {
    var ck = county + '|' + _fKey;
    if (_adKey === ck && _adCache) return _adCache;
    var have = {};
    districtGroups().forEach(function (g) { if (g.county === county) have[g.key] = g; });
    var out = [], ds = (D.map && D.map.districts) || [];
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].county !== county) continue;
      var key = county + '|' + ds[i].district;
      if (have[key]) { out.push(have[key]); continue; }
      var pb = polyBBox(key);
      if (!pb) continue;
      out.push({ key: key, county: county, district: ds[i].district,
                 n: 0, np: 0, med: null, items: [], placed: [],
                 x: (pb[0] + pb[2]) / 2, y: (pb[1] + pb[3]) / 2, bb: pb.slice(),
                 empty: true });
    }
    _adKey = ck; _adCache = out;
    return out;
  }

  // Counties, on the same terms as districts: count and median over EVERY
  // building, centroid and extent over the ones we can place.
  //
  // This is the top of the map's hierarchy. 166 district marks on one national
  // canvas measured 356 overlapping label pairs and 27.9% label ink; 22 county
  // marks is fewer than the 33 the two-city map already handled comfortably.
  var _cgCache = null, _cgKey = null;
  function countyGroups() {
    if (_cgKey === _fKey && _cgCache) return _cgCache;
    var B = filtered(), map = {}, out = [];
    for (var i = 0; i < B.length; i++) {
      var b = B[i], g = map[b.c];
      if (!g) {
        // 市 vs 縣 is the administrative line, and it is also the honest one
        // here: the nine 市 hold 5,916 of 6,043 buildings. The eleven 縣 that
        // have any data at all are mostly under 30 buildings -- 澎湖 has 2,
        // 苗栗 8, 臺東 9 -- so giving them the same mark as 高雄市 would say
        // they are the same kind of thing.
        var nm = countyName(b.c);
        g = map[b.c] = { key: b.c, county: b.c, district: nm, _vb: null,
                         city: nm.charAt(nm.length - 1) === '市',
                         x: 0, y: 0, np: 0, ys: [], items: [], placed: [],
                         bb: [Infinity, Infinity, -Infinity, -Infinity] };
        out.push(g);
      }
      g.ys.push(b.y); g.items.push(b);
      if (b.mx == null) continue;
      g.placed.push(b); g.np++; g.x += b.mx; g.y += b.my;
      if (b.mx < g.bb[0]) g.bb[0] = b.mx;
      if (b.my < g.bb[1]) g.bb[1] = b.my;
      if (b.mx > g.bb[2]) g.bb[2] = b.mx;
      if (b.my > g.bb[3]) g.bb[3] = b.my;
    }
    // A county with no address-point source has no building to average, so it
    // falls back to the centre of its own districts' polygons. Without this the
    // 17 unsourced counties all kept x=y=0 and stacked on top of one another at
    // the origin -- which reads as 基隆市 sitting on 嘉義市, and 苗栗縣 on 屏東縣.
    var LB = D.map.labels || {};
    var poly = {};
    for (var k in LB) {
      if (!Object.prototype.hasOwnProperty.call(LB, k)) continue;
      var c2 = k.split('|')[0], a2 = poly[c2] || (poly[c2] = [0, 0, 0]);
      a2[0] += LB[k][0]; a2[1] += LB[k][1]; a2[2]++;
    }
    for (var j = 0; j < out.length; j++) {
      var o = out[j], n = o.items.length;
      o.n = n;
      if (o.np) {
        o.x /= o.np; o.y /= o.np;
      } else {
        var pb = polyBBox(o.key);
        if (!pb) { o.x = NaN; continue; }
        o.x = (pb[0] + pb[2]) / 2; o.y = (pb[1] + pb[3]) / 2;
        o.bb = pb.slice();
      }
      o.ys.sort(function (p2, q) { return p2 - q; });
      o.med = n % 2 ? o.ys[(n - 1) / 2] : (o.ys[n / 2 - 1] + o.ys[n / 2]) / 2;
    }
    out = out.filter(function (g2) { return isFinite(g2.x) && isFinite(g2.y); });
    _cgKey = _fKey; _cgCache = out;
    return out;
  }

  // The box to FLY to, which is not the same as the box to test for visibility.
  //
  // districtView fitted the full min/max of a group's buildings, so a handful of
  // outliers set the frame: 高雄市 has 2,021 placed buildings across 33 x 45 km,
  // but 96% of them sit in 11 x 24 km — an eighteenth of the area. Opening it
  // put the whole urban core, where every reader is going, into a corner while
  // most of the screen showed mountains with three dots on them.
  //
  // Trimmed to the 2nd-98th percentile on each axis. Small groups keep their
  // full extent, because a percentile of nine buildings is noise.
  function viewBB(g) {
    if (g._vb) return g._vb;
    var pts = g.items || [];
    var xs = [], ys = [], i;
    for (i = 0; i < pts.length; i++) {
      if (pts[i].mx == null) continue;
      xs.push(pts[i].mx); ys.push(pts[i].my);
    }
    if (xs.length < 40) { g._vb = g.bb; return g._vb; }
    xs.sort(function (a, b) { return a - b; });
    ys.sort(function (a, b) { return a - b; });
    function q(v, p) { return v[Math.min(v.length - 1, Math.floor(v.length * p))]; }
    g._vb = [q(xs, 0.02), q(ys, 0.02), q(xs, 0.98), q(ys, 0.98)];
    return g._vb;
  }

  // Fit the BUILDINGS, not the district polygon. 士林區, 北投區 and 汐止區 are
  // three-quarters mountain: fitting the outline puts a ridge on screen and the
  // housing in one corner. The 900 m floor stops a district with two matched
  // buildings from slamming to street level.
  function districtView(g) {
    var vb = viewBB(g);
    var x0 = vb[0], y0 = vb[1], x1 = vb[2], y1 = vb[3];
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    if (x1 - x0 < 900) { x0 = cx - 450; x1 = cx + 450; }
    if (y1 - y0 < 900) { y0 = cy - 450; y1 = cy + 450; }
    return fitBox(x0, y0, x1, y1, 0.22);
  }


  // The natural ending of the coverage argument: the coverage section says
  // 6.22%, this one says what 6.22% permits anyone to claim. Bounds only --
  // no midpoint tick, no centre gridline, and the matched point drawn INSIDE
  // each bar so it cannot be read as the answer.
  function secPartialId() {
    var p = D.partial_id;
    if (!p || !p.rungs || p.rungs.length < 3) return '';
    var sc = p.scope, R = {}; p.rungs.forEach(function (r) { R[r.key] = r; });
    var head = R[p.headline_rung]; if (!head) return '';
    var band = R.band, trim = R.type_trim, age = R.type_price_age;
    var mp = p.matched_point, comp = {};
    (p.composition || []).forEach(function (c) { comp[c.type] = c; });
    function f2(v) { return v == null ? '--' : v.toFixed(2); }

    // the ladder: one bar per rung, labelled at BOTH ends -> natural width
    var rows = p.rungs.concat((p.mts || []).map(function (m) {
      return { key: m.key, gross: m.gross, is_mts: true };
    }));
    // The rung label sits ABOVE its bar, not to its left: a left gutter wide
    // enough for the longest sentence in either language would leave the bars
    // no room, and a label longer than the gutter clips off the canvas.
    var W = 620, padL = 46, padR = 58, RH = 46, padT = 16;
    var H = padT + rows.length * RH + 24;
    var lo0 = band.gross.lo, hi0 = band.gross.hi, PW = W - padL - padR;
    var X = function (v) { return padL + (v - lo0) / (hi0 - lo0) * PW; };
    var body = '';
    [0, 2, 4, 6, 8, 10, 12].forEach(function (t) {
      if (t < lo0 || t > hi0) return;
      body += line(X(t), padT + 10, X(t), H - 22, 'var(--grid)', 1) +
        txt(X(t), H - 8, t + '%', 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:10px"');
    });
    rows.forEach(function (r, i) {
      var y = padT + i * RH, g = r.gross;
      if (!g || g.lo == null) return;
      var x1 = X(g.lo), x2 = X(g.hi);
      var lab = S('pidR_' + r.key) === 'pidR_' + r.key ? r.key : S('pidR_' + r.key);
      if (r.is_mts) lab = (r.key === 'mts_up' ? '↑ ' : '↓ ') + lab;
      body += txt(padL, y + 10, lab, 'hs-glab', 'start',
                  r.is_mts ? ' style="fill:var(--subtle)"' : '') +
        rect(x1, y + 18, Math.max(2, x2 - x1), 16,
             r.is_mts ? 'url(#hxbarL)' : (r.key === p.headline_rung ? 'url(#hxbar)' : 'none'),
             ' stroke="var(--text)" stroke-width="' + (r.key === p.headline_rung ? 1.2 : 0.9) + '"' +
             (r.is_mts ? ' opacity=".6"' : '')) +
        // the matched median as a tick INSIDE the bar, never a bar of its own
        (mp && mp.gross >= g.lo && mp.gross <= g.hi
          ? line(X(mp.gross), y + 16, X(mp.gross), y + 36, 'var(--text)', 1.4)
          : '') +
        // A bar that starts at the axis leaves no room outside it for the low
        // label, and it would land on top of the row label; put it inside.
        (x1 - padL < 40
          ? txt(x1 + 5, y + 30, g.lo.toFixed(2), 'hs-vlab', 'start', ' style="font-size:10px"')
          : txt(x1 - 4, y + 30, g.lo.toFixed(2), 'hs-vlab', 'end', ' style="font-size:10px"')) +
        txt(x2 + 4, y + 30, g.hi.toFixed(2), 'hs-vlab', 'start', ' style="font-size:10px"') +
        (r.buys_pp == null ? '' :
          txt(W - 6, y + 10, Sf(r.buys_pp >= 0 ? 'pidBuys' : 'pidWider',
              Math.abs(r.buys_pp).toFixed(2)), 'hs-glab', 'end',
              ' style="fill:var(--subtle);font-size:9.5px"'));
    });
    var fig1 = fig(S('pidFigT'), Sf('pidFigS', f2(lo0), f2(hi0), f2(mp.gross), n0(sc.matched)),
                   svg(W, H, body, 'hs-axis'));

    var tw = comp['住宅大樓'] || {}, wu = comp['公寓'] || {};
    var un = (p.unanswerable || [])[0] || {};
    var dh = D.walkup_resolution && D.walkup_resolution.precision;
    var mts = {}; (p.mts || []).forEach(function (m) { mts[m.key] = m; });
    var ci = p.endpoint_ci;
    return sec('pidEy', null, 0,
      '<h2>' + esc(Sf('pidH', f2(sc.coverage_pct), f2(100 - sc.coverage_pct))) + '</h2>' +
      '<p class="hs-prose lede">' + esc(Sf('pidLede', n0(sc.matched), n0(sc.n),
        n0(sc.n - sc.matched), f2(sc.coverage_pct))) + '</p>' +
      '<div class="hs-callout"><p>' + esc(Sf('pidWhy', f2(sc.coverage_pct), f2(p.ceiling_pct))) + '</p></div>' +
      '<p class="hs-prose">' + esc(Sf('pidScope', n0(sc.n))) + '</p>' +
      fig1 +
      '<p class="hs-prose">' + esc(Sf('pidTrimWarn', Math.abs(trim.buys_pp).toFixed(2))) + '</p>' +
      (age ? '<p class="hs-prose">' + esc(Sf('pidAgeWarn', n0(age.cells_below_min), n0(age.cells),
        n0(p.min_cell), n0(age.fellback_universe_n), Math.abs(age.buys_pp).toFixed(2))) + '</p>' : '') +
      (mts.mts_up && mts.mts_down ? '<p class="hs-prose">' + esc(Sf('pidMts',
        (p.ppp_gap_pct == null ? (D.age && D.age.ppp_diff_pct) : p.ppp_gap_pct),
        f2(mts.mts_up.gross.lo), f2(mts.mts_up.gross.hi),
        f2(mts.mts_down.gross.lo), f2(mts.mts_down.gross.hi))) + '</p>' : '') +
      '<p class="hs-prose">' + esc(Sf('pidComp', f2(tw.universe_share_pct), f2(tw.matched_share_pct),
        f2(tw.match_rate_pct), f2(wu.universe_share_pct), f2(wu.matched_share_pct),
        f2(wu.match_rate_pct))) + '</p>' +
      (un.support ? '<p class="hs-prose">' + esc(Sf('pidUnans', un.type, f2(un.coverage_pct),
        f2(un.support[0]), f2(un.support[1]), f2(un.width),
        dh ? f2(dh.gross_gap) : '--')) + '</p>' : '') +
      '<p class="hs-plain">' + esc(Sf('pidMid', n0(sc.matched), f2(mp.gross))) + '</p>' +
      (MODE === 'advanced' && ci ? '<p class="hs-fig-n hs-prose">' + esc(Sf('pidCI',
        f2(ci.lo_ci[0]), f2(ci.lo_ci[1]), f2(ci.hi_ci[0]), f2(ci.hi_ci[1]), n0(ci.n_boot))) + '</p>' : ''));
  }

  function secMap() {
    var M = D.map;
    var home = mapHome();
    if (!M || !home) return '';
    var V = _mapV || home;
    var B = filtered().filter(function (b) { return b.mx != null; });
    // The height attribute has to track mapAR(). With `height: auto` in CSS an
    // SVG takes its intrinsic ratio from the width/height ATTRIBUTES, not from
    // the viewBox -- so a hard-coded 640 pinned the surface to landscape and the
    // portrait mobile box was silently ignored.
    var W = MAP_W, H = Math.round(MAP_W / mapAR());
    var base = M.base || {};
    var Q = base.quant || 4;

    function layer(d, cls) {
      if (!d) return '';
      return '<g transform="scale(' + Q + ',' + Q + ')" class="' + cls + '">' +
        '<path d="' + d + '"/></g>';
    }
    var water = _layers.water
      ? layer(base.water, 'hs-water') + layer(base.river, 'hs-river') : '';
    var roads = _layers.roads
      ? layer(base.secondary, 'hs-rd2') + layer(base.major, 'hs-rd1') : '';
    var mrt = _layers.mrt ? layer(base.mrt, 'hs-mrt') : '';

    // The polygon carries the district's MEDIAN yield. It used to be one flat
    // surface colour behind a hairline border, so on a dark map 33 districts
    // read as a single shape -- and the value they were being asked to show was
    // carried instead by a disc drawn on top, covering the geography. A
    // choropleth puts the value on the area, which is where an area map wants
    // it, and makes each district visibly a different place from the next.
    var dmed = {};
    districtGroups().forEach(function (dg) { dmed[dg.key] = dg; });
    var FLOOR0 = (D.meta && D.meta.min_district_n) || 25;
    var dmedByCounty = {};
    countyGroups().forEach(function (cg) {
      if (cg.n >= FLOOR0) dmedByCounty[cg.key] = yieldFillAt(cg.med, 0);
    });

    // Boundaries are built here but drawn in their OWN layer, above the roads
    // and the density grid. Stroked as part of the fill they were buried by
    // both, which is exactly why the separation was invisible.
    //
    // The casing that lets one line colour read over both ends of the ramp is
    // the FILL layer's own stroke (see .hs-land in the CSS), not a third copy of
    // every ring. Drawn as its own layer it tripled the boundary vertex count,
    // which is survivable for 41 districts and is not for 365.
    var edges = [];
    var land = (M.districts || []).map(function (d) {
      var dk = d.county + '|' + d.district;
      var on = state.district === dk;
      var path = d.rings.map(function (r) {
        return 'M' + r.map(function (p) { return p[0] + ' ' + p[1]; }).join('L') + 'Z';
      }).join(' ');
      edges.push('<path class="hs-bound" d="' + path + '" data-dkey="' + esc(dk) + '"/>');
      // A district with nothing to count is BARE PAPER — no tone at all, not
      // the palest step. That distinction is the hard rule on this map: "we
      // could not measure this" must never look like "we measured this and it
      // was low." It is why the map was rebuilt once already, after 嘉義縣 was
      // painted the darkest county in the country off 18 buildings.
      //
      // It was previously filled --surface3 because an unfilled district read
      // as a hole punched through the picture. That reasoning applied to a
      // choropleth of flat colour; it does not apply here. The boundary still
      // draws in its own layer, so an untextured district is an OUTLINED EMPTY
      // AREA, which is a shape a reader already knows how to read — and against
      // a page where every measured thing is hatched, the absence of texture is
      // the loudest possible way to say there is nothing to measure.
      return '<path class="hs-land' + (on ? ' on' : '') + (dmed[dk] ? '' : ' nodata') +
        '" d="' + path + '" data-dkey="' + esc(dk) + '" fill="' +
        (dmed[dk] ? yieldFillAt(dmed[dk].med, 1) : 'none') + '"/>';
    }).join('');
    var bounds = '<g class="hs-bounds">' + edges.join('') + '</g>';

    // The COUNTY layer, drawn over the district one and shown only at national
    // zoom. A city is one block there: painting its districts the same colour is
    // not enough on its own, because the borders between them still draw and
    // 臺南市 reads as 37 tiles. This is a real dissolved outline (see
    // boundaries.dissolve_counties), so there is nothing internal left to draw.
    var cland = (M.counties || []).map(function (c) {
      var cp = c.rings.map(function (r) {
        return 'M' + r.map(function (q) { return q[0] + ' ' + q[1]; }).join('L') + 'Z';
      }).join(' ');
      var has = dmedByCounty[c.county];
      return '<path class="hs-cland' + (has ? '' : ' nodata') + '" d="' + cp +
        '" data-dkey="' + esc(c.county) + '" fill="' +
        (has || 'none') + '"/>' +
        '<path class="hs-cbound" d="' + cp + '"/>';
    }).join('');
    var countyLayer = '<g class="hs-counties" id="hs-counties">' + cland + '</g>';

    // 2,000 individual <rect> were 2,000 nodes to lay out on every frame.
    // Bucketing the density into five opacity bands and emitting one <path>
    // per band gives the same picture in five nodes.
    var g = M.grid, cells = '';
    if (g && g.cells && _layers.dens) {
      var maxN = 1;
      g.cells.forEach(function (c) { if (c[2] > maxN) maxN = c[2]; });
      var bands = [[], [], [], [], []];
      g.cells.forEach(function (c) {
        var bi = Math.min(4, Math.floor(Math.sqrt(c[2] / maxN) * 5));
        var x = g.x0 + c[0] * g.cell, y = g.y0 + c[1] * g.cell;
        bands[bi].push('M' + x + ' ' + y + 'h' + g.cell + 'v' + g.cell + 'h' + (-g.cell) + 'Z');
      });
      cells = '<g class="hs-dens">' + bands.map(function (bd, i) {
        return bd.length ? '<path d="' + bd.join('') + '" opacity="' +
          (0.06 + 0.20 * ((i + 0.5) / 5)).toFixed(2) + '"/>' : '';
      }).join('') + '</g>';
    }

    var stations = (_layers.mrt && base.stations) ? base.stations.map(function (st) {
      return '<circle class="hs-stn" cx="' + (st[0] * Q) + '" cy="' + (st[1] * Q) + '" r="60"/>';
    }).join('') : '';

    var labels = _layers.labels ? Object.keys(M.labels || {}).map(function (k) {
      var p = M.labels[k];
      return '<text class="hs-dlabel" data-dk="' + esc(k) + '" x="' + p[0] + '" y="' + p[1] +
        '" text-anchor="middle" transform="scale(1,-1) translate(0,' + (-2 * p[1]) + ')">' +
        esc(k.split('|')[1]) + '</text>';
    }).join('') : '';

    var stnLabels = (_layers.mrt && base.stations) ? base.stations.map(function (st) {
      var x = st[0] * Q, y = st[1] * Q;
      return '<text class="hs-stnlab" x="' + x + '" y="' + y +
        '" text-anchor="middle" transform="scale(1,-1) translate(0,' + (-2 * y) + ')">' +
        esc(st[2]) + '</text>';
    }).join('') : '';

    var sym = TYPES.map(function (t) {
      return '<span class="hs-symrow"><svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true" focusable="false">' +
        symbolPath(t, 0, 0, 3.8) + ' fill="var(--muted)"/></svg>' + esc(typeLabel(t)) + '</span>';
    }).join('');

    var legend =
      '<div class="hs-maplegend">' +
        '<b id="hs-ramplab">' + esc(S('rampLegC')) + '</b>' +
        // Six discrete bands, not a gradient: the map is drawn in six discrete
        // steps, and a smooth key for a stepped map tells the reader the scale
        // is continuous when it is not.
        '<div class="hs-ramp"><i class="hs-y1"></i><i class="hs-y2"></i>' +
          '<i class="hs-y3"></i><i class="hs-y4"></i><i class="hs-y5"></i>' +
          '<i class="hs-y6"></i></div>' +
        '<div class="hs-ramp-ax" id="hs-rampax"></div>' +
        '<details><summary>' + esc(S('mapTypeLbl')) + '</summary>' + sym +
          '<p class="hs-exlab">' + esc(S('numLeg')) + '</p>' +
          '<p class="hs-exlab">' + esc(S('exclLeg')) + '</p>' +
        '</details>' +
      '</div>';

    var menu = '<span class="hs-lay"><button type="button" class="hs-chip" id="hs-laybtn" ' +
      'aria-expanded="false">' + esc(S('layersBtn')) + ' &#9662;</button>' +
      '<div class="hs-laymenu" id="hs-laymenu" hidden>' +
      [['excl', 'layExcl'], ['roads', 'layRoads'], ['mrt', 'layMrt'],
       ['water', 'layWater'], ['dens', 'layDens'], ['labels', 'layLabels']].map(function (t) {
        return '<label><input type="checkbox" data-layer="' + t[0] + '"' +
          (_layers[t[0]] ? ' checked' : '') + '>' + esc(S(t[1])) + '</label>';
      }).join('') +
      // The basemap is staged by zoom, so three of these five do nothing at full
      // extent. A toggle that visibly does nothing reads as a broken toggle.
      '<p class="hs-laynote">' + esc(S('layZoomNote')) + '</p>' +
      '</div></span>';

    // The focus pill lives INSIDE the map, not in the header: once you are zoomed
    // into a district the header has scrolled away, and nothing else on screen
    // names the district you are looking at. It is filled in by commit(), because
    // opening a district must not cost a full rerender.
    // title= is a tooltip, not an accessible name; the button is empty until
    // the map zooms in and its text is filled by script, so it needs a label
    var back = '<button type="button" class="hs-focuspill" id="hs-mapback" hidden aria-label="' + esc(S('mapAll')) + '" ' +
      'title="' + esc(S('mapAll')) + '"></button>';

    // Search lives ON the map, not above it: the map is the thing it moves, and
    // by the time a reader has scrolled the header away it is the only way in
    // that is still on screen. The table's own search is a different control for
    // a different job and stays where it is.
    var find = '<div class="hs-msearch">' +
      '<input type="search" id="hs-msq" autocomplete="off" spellcheck="false" ' +
        'placeholder="' + esc(S('msearch')) + '" aria-label="' + esc(S('msearch')) + '">' +
      '<ul class="hs-msres" id="hs-msres" hidden></ul></div>';

    var ctl =
      '<div class="hs-mapctl">' +
        '<button type="button" data-zoom="in" aria-label="zoom in">+</button>' +
        '<button type="button" data-zoom="out" aria-label="zoom out">&minus;</button>' +
        '<button type="button" class="wide" data-zoom="home">' + esc(S('mapReset')) + '</button>' +
      '</div>';

    // Marks live in their own <g> so a zoom can redraw ONLY them. Re-clustering
    // used to call rerender(), which rebuilt all 14 sections including a
    // 600-row table and a 2,541-point scatter: 425 ms to move ~100 circles.
    var excl = '<g id="hs-excl">' + exclHtml(V.w / W, V) + '</g>';
    var marks = '<g id="hs-marks">' + marksHtml(V.w / W, V) + '</g>';

    return sec('mapEy', null, 0,
      '<h2>' + esc(Sf('mapH', n0(D.headline.buildings))) + '</h2>' +
      '<p class="hs-prose">' + esc(Sf('mapIntro', n0(B.length),
        n0(D.headline.buildings - B.length))) + ' ' +
        '<button class="hs-howlink" data-goto="cov">' + esc(S('mapHow')) + ' &rarr;</button></p>' +
      '<div class="hs-maphead">' + menu + mapFilters() +
        '<span class="hs-mono-s" id="hs-hint">' + esc(S('hint0')) + '</span></div>' +
      '<div class="hs-mapwrap" id="hs-map">' +
        '<svg id="hs-mapsvg" viewBox="' + V.x + ' ' + V.y + ' ' + V.w + ' ' + V.h + '" ' +
          'width="' + W + '" height="' + H + '" preserveAspectRatio="xMidYMid meet" ' +
          'role="application" aria-label="' + esc(S('mapAria')) + '">' +
          hatchDefs() +
          '<g transform="scale(1,-1)">' + land + water + cells + roads + mrt +
            stations + bounds + countyLayer + excl + marks + labels + stnLabels + '</g>' +
        '</svg>' + back + find + legend + ctl +
        '<div class="hs-scalebar" id="hs-scale"><i></i><span></span></div>' +
        '<aside class="hs-panel" id="hs-panel" aria-live="polite"></aside>' +
      '</div>' +
      '<div class="hs-fig-n">' + esc(Sf('mapGeo', (D.meta.geo && D.meta.geo.rate) || 0,
          geoSplit().high, geoSplit().midName || '—',
          geoSplit().midPct != null ? geoSplit().midPct.toFixed(0) : '--',
          geoSplit().none)) +
        ' ' + esc(S('mapAttrib')) + '</div>');
  }

  // Below this viewBox width a district is filling the screen, so its label
  // stops being a summary and starts being an obstruction: every district in
  // view opens on its own. Above it, only the one you clicked is open.
  var DETAIL_W = 12000;
  // COUNTY -> DISTRICT -> BUILDING. `c` is a county letter, `d` a
  // 'county|district' key. Nothing focused = the national county view.
  var _focus = { c: null, d: null };
  var _level = 0;           // 0 county, 1 district, 2 building — set by marksHtml
  var _labelKeys = {};      // districts currently drawn as a label, for the labels layer
  function focusKey() { return (_focus.c || '') + '>' + (_focus.d || ''); }

  // Marks are UNIFORM ink, and that is a deliberate demotion, not an oversight.
  // A single building's yield is one sale matched to one lease -- the noisiest
  // number the payload contains, and the one the whole page argues against
  // over-reading. Painting 2,000 of them on a six-step ramp invites exactly
  // that reading, at the zoom level where the reader is closest and most
  // inclined to believe it. The district median underneath is what the page is
  // willing to rank (n >= 25); the individual figure is one click away, where
  // it arrives with its address and its dates attached.
  //
  // 建物型態 survives intact: symbolPath() already encodes it as circle /
  // diamond / square, so the three series colours were redundant with shape
  // before this restyle and cost nothing on the way out.
  function dotsHtml(g, mpp) {
    var r = 4.1 * mpp, sw = (0.6 * mpp).toFixed(1), out = [];
    for (var i = 0; i < g.placed.length; i++) {
      var b = g.placed[i];
      out.push(symbolPath(b.t, b.mx, b.my, r) + ' class="hs-mdot" data-b="' +
        esc(b.a) + '" tabindex="0" role="button" aria-label="' +
        esc(Sf('ariaBld', b.a, b.y.toFixed(2))) + '" fill="var(--text)"' +
        ' stroke-width="' + sw + '"/>');
    }
    return out.join('');
  }

  // The mark is the NUMBER, with the district's name under it.
  //
  // It used to be a filled disc with the count inside it -- the conventional
  // cluster glyph, and wrong twice over here. 33 discs cover the geography the
  // map exists to show, and the disc was spending its fill on a value the
  // polygon underneath can carry for free. The polygon is the choropleth now;
  // the mark is type, and type does not occlude.
  //
  // Size still carries the count, and still by sqrt, so 271 is not ten times the
  // visual weight of 27 -- as a font size rather than as an area.
  function countSize(n, sc) { return (10 + Math.min(9, Math.sqrt(n) * 1.0)) * sc; }

  // Sizes are in PIXELS, so on a 341 px phone canvas the same label covers three
  // times the share of the map that it does on an 880 px desktop one. Scale the
  // whole block to the canvas, with a floor so the number stays readable.
  function markScale(cw) { return Math.max(0.72, Math.min(1, cw / 760)); }

  // Half-extent of the two-line block in WORLD metres, plus the two font sizes in
  // px. A CJK glyph is about 1 em wide, which is why a three-character district
  // name is wider than any count it will ever carry.
  function labelBox(g, mpp, sc) {
    if (g.quiet) {
      var qf = 10 * sc;
      return { quiet: true, cf: 0, nf: qf,
               hw: g.district.length * qf * 1.02 / 2 * mpp, hh: qf * 1.18 / 2 * mpp };
    }
    var cf = countSize(g.n, sc), nf = 10.5 * sc;
    var w = Math.max(String(g.n).length * cf * 0.62, g.district.length * nf * 1.02);
    // 1.32 and 1.18, not 1.0: ascenders and descenders run past the font size, so
    // modelling a line as exactly its font-size left eight pairs of blocks
    // grazing each other by about a pixel.
    return { cf: cf, nf: nf, hw: w / 2 * mpp, hh: (cf * 1.32 + nf * 1.18) / 2 * mpp };
  }

  // Labels are DISPLACED apart, and never dropped.
  //
  // The badge layout dropped every name it could not place -- 9 of 33 at full
  // extent -- so the districts a reader most wants named, the dense ones in the
  // core, were the anonymous numbers. The name is part of the mark now, so the
  // layout has to make room rather than give up: blocks are separated along
  // whichever axis needs the least movement, which for something wide and short
  // is almost always the vertical one.
  //
  // Displacement stays leashed. The name says which district it is, so a bounded
  // move is ordinary cartographic practice; an unbounded one would let a name
  // drift into the next city.
  function layoutLabels(gs, mpp, sc, vp) {
    var n = gs.length, P = new Array(n), i, j, it;
    for (i = 0; i < n; i++) {
      var m = labelBox(gs[i], mpp, sc);
      P[i] = { x: gs[i].x, y: gs[i].y, ox: gs[i].x, oy: gs[i].y,
               hw: m.hw, hh: m.hh, cf: m.cf, nf: m.nf, quiet: m.quiet };
    }
    var GAP = 5 * sc * mpp;
    // A smaller canvas needs a longer leash: the blocks are a bigger share of it,
    // so they have further to travel before they stop touching.
    var LEASH = sc < 0.95 ? 3.2 : 2.2;
    for (it = 0; it < 160; it++) {
      var moved = false;
      for (i = 0; i < n; i++) {
        for (j = i + 1; j < n; j++) {
          var a = P[i], b = P[j];
          var dx = b.x - a.x, dy = b.y - a.y;
          var ox = a.hw + b.hw + GAP - Math.abs(dx);
          var oy = a.hh + b.hh + GAP - Math.abs(dy);
          if (ox <= 0 || oy <= 0) continue;
          if (ox / (a.hw + b.hw) < oy / (a.hh + b.hh)) {
            var px = (dx < 0 ? -1 : 1) * ox / 2;
            a.x -= px; b.x += px;
          } else {
            var py = (dy < 0 ? -1 : 1) * oy / 2;
            a.y -= py; b.y += py;
          }
          moved = true;
        }
      }
      for (i = 0; i < n; i++) {
        var q = P[i], ex = q.x - q.ox, ey = q.y - q.oy;
        var e = Math.sqrt(ex * ex + ey * ey), lim = Math.max(q.hw, q.hh) * LEASH;
        if (e > lim) { q.x = q.ox + ex / e * lim; q.y = q.oy + ey / e * lim; }
        // ...and inside the canvas. Displacement alone pushed 基隆市 seven pixels
        // off the top edge, 屏東縣 off the bottom and 澎湖縣 off the left — three
        // marks that simply were not on the map, one of them a city. A name half
        // off the edge is worse than a name moved a little further.
        if (vp) {
          // Inset rather than flush: a mark clamped hard to the top edge sits
          // under the page's sticky header at most scroll positions, which is
          // how 基隆市 stayed invisible even after it was technically on-canvas.
          var ix = (vp[2] - vp[0]) * 0.02, iy = (vp[3] - vp[1]) * 0.02;
          q.x = Math.min(Math.max(q.x, vp[0] + q.hw + ix), vp[2] - q.hw - ix);
          q.y = Math.min(Math.max(q.y, vp[1] + q.hh + iy), vp[3] - q.hh - iy);
        }
      }
      if (!moved) break;
    }
    return P;
  }

  // A district with no matched pair has no median. Formatting it threw
  // TypeError: Cannot read properties of null (reading 'toFixed') INSIDE
  // marksHtml, which aborted the whole rebuild -- so the map kept the previous
  // level's marks and looked like the click had done nothing, while _focus and
  // _level had both in fact moved. Every empty district triggered it, which is
  // why 臺北市 (all 12 of its districts have data) was the only city that opened.
  function medAttr(g) { return g.med == null ? '' : g.med.toFixed(2); }

  // A mark is a control, so it says so and can be reached. The set is bounded by
  // construction -- 22 counties, or one county's districts -- so this is at most
  // ~40 tab stops, not 365.
  function markA11y(g) {
    var lab = g.med == null ? Sf('ariaMarkNo', g.district)
      : Sf('ariaMark', g.district, n0(g.n), g.med.toFixed(2));
    return ' tabindex="0" role="button" aria-label="' + esc(lab) + '"';
  }

  function labelHtml(g, p, mpp) {
    // World y grows north and this text sits inside scale(1,-1), so it is
    // flipped back upright -- after which dy measures DOWN the screen.
    var fx = p.x.toFixed(0), fy = p.y.toFixed(0), flip = (-2 * p.y).toFixed(0);
    var cf = p.cf * mpp, nf = p.nf * mpp, H = cf * 1.18 + nf;
    function line(cls, size, dy, txt) {
      return '<text class="' + cls + '" x="' + fx + '" y="' + fy + '" font-size="' +
        size.toFixed(0) + '" transform="scale(1,-1) translate(0,' + flip +
        ')" dy="' + dy.toFixed(0) + '">' + txt + '</text>';
    }
    // A glyph's own ink is a thin and unreliable thing to ask a thumb to hit, so
    // the hit target is one transparent rect over the whole block.
    // 40x33 css px measured on a 375px screen, under the 44px touch guideline.
    // The pad is in world units, so it scales with the mark: widen it where the
    // mark is smallest.
    var pad = (p.quiet ? 7 : 5) * mpp;
    if (p.quiet) {
      return '<g class="hs-dg quiet" data-key="' + esc(g.key) + '" data-dname="' +
        esc(g.district) + '" data-kind="county" data-n="' + g.n +
        '" data-med="' + medAttr(g) + '"' + markA11y(g) + '>' +
        '<rect class="hs-dhit" x="' + (p.x - p.hw - pad).toFixed(0) + '" y="' +
          (p.y - p.hh - pad).toFixed(0) + '" width="' + (2 * p.hw + 2 * pad).toFixed(0) +
          '" height="' + (2 * p.hh + 2 * pad).toFixed(0) + '"/>' +
          line('hs-dgname', nf, nf * 0.39, esc(g.district)) +
        (g.n ? line('hs-dgnum', nf * 0.92, nf * 1.42, n0(g.n)) : '') +
      '</g>';
    }
    return '<g class="hs-dg" data-key="' + esc(g.key) + '" data-dname="' + esc(g.district) +
      '" data-kind="' + (g.key.indexOf('|') < 0 ? 'county' : 'district') +
      '" data-n="' + g.n + '" data-med="' + medAttr(g) + '"' + markA11y(g) + '>' +
      '<rect class="hs-dhit" x="' + (p.x - p.hw - pad).toFixed(0) + '" y="' +
        (p.y - p.hh - pad).toFixed(0) + '" width="' + (2 * p.hw + 2 * pad).toFixed(0) +
        '" height="' + (2 * p.hh + 2 * pad).toFixed(0) + '"/>' +
      line('hs-dcount', cf, -H / 2 + 0.78 * cf, g.n) +
      line('hs-dgname', nf, -H / 2 + 1.18 * cf + 0.78 * nf, esc(g.district)) +
    '</g>';
  }

  // Buildings that have BOTH records and are still not priced.
  //
  // The map draws 6,043 of 157,594 buildings and reads as empty, which is
  // true and unhelpful on its own. 113,761 of the missing have no lease record
  // at all — there is no rent, so there is nothing to draw. The other 31,812 do
  // have both and are removed by our own filters, and those CAN be drawn. Doing
  // so is the site's argument made visible: the map fills in, and every added
  // building is one the method had to throw away.
  //
  // One <path> per reason, not one node per building. 31,812 elements would be
  // a DOM the browser has to lay out; three paths of tiny squares is three.
  var EXCL_W = 40000;      // inside a county, roughly
  function exclHtml(mpp, V) {
    var E = D.map && D.map.excluded;
    if (!E || !E.length || !_layers.excl || !V || V.w > EXCL_W) return '';
    var m = V.w * 0.15;
    var x0 = V.x - m, x1 = V.x + V.w + m;
    var y0 = -(V.y + V.h) - m, y1 = -V.y + m;
    var r = Math.max(1.6, 2.6 * mpp), d = ['', '', '', ''];
    for (var i = 0; i < E.length; i++) {
      var e = E[i], x = e[0], y = e[1];
      if (x < x0 || x > x1 || y < y0 || y > y1) continue;
      d[e[3]] += 'M' + (x - r).toFixed(0) + ' ' + (y - r).toFixed(0) +
        'h' + (2 * r).toFixed(0) + 'v' + (2 * r).toFixed(0) +
        'h' + (-2 * r).toFixed(0) + 'Z';
    }
    var out = '';
    for (var w = 1; w <= 3; w++) {
      if (d[w]) out += '<path class="hs-ex hs-ex' + w + '" d="' + d[w] + '"/>';
    }
    return out;
  }

  // ── map search ────────────────────────────────────────────────────────
  //
  // Three kinds of answer from one box, ranked so the biggest thing you could
  // have meant comes first: a county, a district, then an individual building.
  // Matching is plain substring over strings the reader can actually see, and
  // 台/臺 is folded because a person typing 台中 should not have to know that
  // the registry writes 臺中.
  function tw(v) { return (v || '').replace(/台/g, '臺'); }

  function mapSearch(q) {
    q = tw(String(q || '').trim());
    if (q.length < 1) return [];
    var out = [], seen = {};
    countyGroups().forEach(function (g) {
      if (tw(g.district).indexOf(q) < 0) return;
      out.push({ kind: 'county', key: g.key, label: g.district, n: g.n });
    });
    districtGroups().forEach(function (g) {
      if (tw(g.district).indexOf(q) < 0) return;
      out.push({ kind: 'district', key: g.key, label: g.district,
                 sub: countyName(g.county), n: g.n });
    });
    // Buildings last, and capped: 6,043 addresses will happily match "路".
    var B = filtered();
    for (var i = 0; i < B.length && out.length < 24; i++) {
      var b = B[i];
      if (b.mx == null || seen[b.a] || tw(b.a).indexOf(q) < 0) continue;
      seen[b.a] = 1;
      out.push({ kind: 'building', key: b.a, label: b.a,
                 sub: countyName(b.c) + ' ' + b.d, y: b.y });
    }
    return out.slice(0, 8);
  }

  function marksHtml(mpp, V) {
    // Viewport in WORLD coordinates: the viewBox y runs the other way because
    // the whole drawing sits inside scale(1,-1).
    var m = V ? V.w * 0.25 : 0;
    var vx0 = V ? V.x - m : -Infinity, vx1 = V ? V.x + V.w + m : Infinity;
    var vy0 = V ? -(V.y + V.h) - m : -Infinity, vy1 = V ? -V.y + m : Infinity;
    function near(g) {
      return g.bb[2] >= vx0 && g.bb[0] <= vx1 && g.bb[3] >= vy0 && g.bb[1] <= vy1;
    }
    _labelKeys = {};
    var dots = [], labs = [];

    if (!_focus.c) {
      // ── COUNTY. The whole country.
      //
      // The nine 市 get the full mark -- count above, name below. The 縣 get
      // their name only, smaller and quieter: they are still there, still
      // named and still clickable, but they no longer claim the same weight as
      // a city holding two hundred times as many buildings.
      _level = 0;
      labs = countyGroups().map(function (g) {
        return g.city ? g : Object.assign({}, g, { quiet: true });
      });
    } else {
      _level = _focus.d ? 2 : 1;
      // Every district of the focused county is a candidate mark; the rest of
      // the country stays as county marks so the reader can step sideways
      // without going home first.
      var inCounty = allDistricts(_focus.c);
      countyGroups().forEach(function (g) {
        // Other counties stay on the map so a reader can step sideways, but
        // QUIETLY. Drawn at full weight they compete with the districts of the
        // county actually open: 臺南市's 814 sat next to 高雄's 332 in the same
        // type, inviting the reader to compare a whole city with one district.
        if (g.key !== _focus.c) labs.push(Object.assign({}, g, { quiet: true }));
      });
      // A focused district is the ONLY housing on the map. Below DETAIL_W a
      // district fills the screen, so any district in view opens on its own --
      // but never while one is explicitly focused, or its neighbours bury it.
      var detail = !_focus.d && !!V && V.w < DETAIL_W;
      inCounty.forEach(function (g) {
        if ((g.key === _focus.d || (detail && near(g))) && g.np) {
          return dots.push(dotsHtml(g, mpp));
        }
        _labelKeys[g.key] = 1;
        // Nothing matched here, so there is no number to show. Same treatment as
        // a 縣 at national zoom: named, quieter, still a door.
        labs.push(g.empty ? Object.assign({}, g, { quiet: true }) : g);
      });
    }

    // Drop marks that are not on screen BEFORE laying out, because the clamp
    // inside layoutLabels would otherwise drag them in. Zoomed into 三民區 that
    // meant 37 other 高雄 districts and 19 other counties being hauled into a
    // 1 km viewport and stacked: 417 overlapping pairs out of 56 marks. A mark
    // for somewhere you cannot see is not a mark, it is a collision.
    // At national zoom nothing is dropped -- everything is already in view --
    // which is where the clamp is genuinely needed.
    if (V) labs = labs.filter(near);
    var sc = markScale(V ? V.w / mpp : MAP_W);
    // The viewport in WORLD units, for the clamp inside layoutLabels.
    var vp = V ? [V.x, -(V.y + V.h), V.x + V.w, -V.y] : null;
    var P = layoutLabels(labs, mpp, sc, vp);
    // Dots first: a label must never be buried under the buildings of the
    // district next to it.
    var out = dots.join('');
    for (var i = 0; i < labs.length; i++) out += labelHtml(labs[i], P[i], mpp);
    return out;
  }

  // ── detail panel ──────────────────────────────────────────────────────
  function openPanel(b) {
    var el = document.getElementById('hs-panel');
    if (!el || !b) return;
    var ny = netYield(b);
    var age = b.b == null ? null : 115 - b.b;
    function row(k, v) { return '<dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd>'; }
    el.innerHTML =
      '<button class="x" data-panel="close" aria-label="' + esc(S('pnlClose')) + '">&times;</button>' +
      '<h4>' + esc(b.a) + '</h4>' +
      '<div class="sub">' + esc(b.d) + ' \u00b7 ' + esc(typeLabel(b.t)) + '</div>' +
      '<div class="big">' + b.y.toFixed(2) + '%</div>' +
      '<div class="biglab">' + esc(S('pnlGross')) + '</div>' +
      '<dl>' +
        row(S('pnlNet'), ny == null ? '--' : ny.toFixed(2) + '%') +
        row(S('pnlPrice'), money(b.pa)) +
        row(S('pnlPPing'), money(b.p)) +
        row(S('pnlRent'), money(b.rm)) +
      '</dl>' +
      '<div class="grp">' + esc(S('pnlBuilding')) + '</div>' +
      '<dl>' +
        row(S('pnlType'), typeLabel(b.t)) +
        (b.fl ? row(S('pnlFloors'), b.fl) : '') +
        (b.b == null ? '' : row(S('pnlBuilt'), b.b)) +
        (age == null ? '' : row(S('pnlAge'), age + ' ' + S('pnlYears'))) +
        row(S('pnlMgr'), b.m ? S('pnlYes') : S('pnlNo')) +
        (b.m ? row(S('pnlMgf'), b.mf ? S('pnlMgfAny') : S('pnlMgfNone')) : '') +
        (b.ro != null && b.ro !== b.rm ? row(S('pnlRentOld'), 'NT$' + n0(b.ro)) : '') +
      '</dl>' +
      '<div class="grp">' + esc(S('pnlMarket')) + '</div>' +
      '<dl>' +
        row(S('pnlPairs'), n0(b.n)) +
        (b.mrt == null ? '' : row(S('pnlMrt'), b.mrts + ' \u00b7 ' + n0(b.mrt) + ' m')) +
      '</dl>' +
      '<div class="foot">' + esc(S('pnlNoVal')) + '</div>';
    el.classList.add('on');
    // The panel is a dialog in everything but name: it appears over the map,
    // it is dismissed, and while it is up it is the thing the reader is
    // reading. Saying so lets a screen reader announce it as one.
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'false');
    el.setAttribute('aria-label', b.a);
    // Remember where the reader was. A mark on the map is a real focus target
    // (it is a button with tabindex), and returning there on close is the
    // difference between dismissing a panel and being dumped at the top of the
    // document with 2,000 marks between you and the one you had opened.
    _panelReturn = (document.activeElement &&
                    document.activeElement !== document.body)
      ? document.activeElement : null;
    var close = el.querySelector('[data-panel="close"]');
    if (close) close.focus();
  }
  // Set by openPanel, consumed by closePanel. Held outside both so a re-render
  // between them cannot lose it.
  var _panelReturn = null;
  function closePanel() {
    var el = document.getElementById('hs-panel');
    if (!el || !el.classList.contains('on')) return false;
    el.classList.remove('on');
    el.innerHTML = '';
    el.removeAttribute('role');
    el.removeAttribute('aria-label');
    var back = _panelReturn;
    _panelReturn = null;
    // isConnected: a re-render can replace the node the reader came from, and
    // focusing a detached element silently sends focus to <body>.
    //
    // That is not a corner case here, it is the COMMON path: opening a building
    // from the map search closes the result list, so by the time the panel
    // shuts, the button the reader came from no longer exists. Verified in the
    // browser — focus went to <body> and the reader was returned to the top of
    // the document with the whole page between them and the map.
    //
    // So there is a fallback, and it is the map rather than nothing: tabindex
    // -1 makes the svg programmatically focusable without putting it in the tab
    // order, and landing there means the next Tab continues from the map.
    if (back && back.isConnected && typeof back.focus === 'function') {
      try { back.focus(); return true; } catch (e) {}
    }
    var sv = document.getElementById('hs-mapsvg');
    if (sv) {
      if (!sv.hasAttribute('tabindex')) sv.setAttribute('tabindex', '-1');
      try { sv.focus(); } catch (e) {}
    }
    return true;
  }

  // The map's own keydown listener lives on the <svg>, and openPanel moves
  // focus into the panel — which is a SIBLING of the svg, so from there the map
  // handler never fires and Escape did nothing. Bound once, at the document, so
  // the key works wherever the reader happens to be standing.
  var _escBound = false;
  function bindPanelEsc() {
    if (_escBound) return;
    _escBound = true;
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      // Let the map handler own Escape while focus is still on the map, so
      // stepping back out a zoom level keeps working exactly as before.
      var t = e.target;
      if (t && t.closest && t.closest('#hs-mapsvg')) return;
      if (closePanel()) e.preventDefault();
    });
  }

  function wireMap() {
    bindPanelEsc();
    var host = document.getElementById('hs-map');
    var sv = document.getElementById('hs-mapsvg');
    if (!host || !sv) return;
    var home = mapHome();
    var V = _mapV || { x: home.x, y: home.y, w: home.w, h: home.h };
    var marksG = document.getElementById('hs-marks');
    var raf = null, pendingMarks = false, lastMarkMpp = null;
    var lastDetail = null, lastPanKey = null, lastFocus = null;

    function width() { return sv.getBoundingClientRect().width || 880; }

    // Everything that touches the DOM on zoom is funnelled through one
    // requestAnimationFrame, so a burst of wheel events costs one paint instead
    // of one paint each.
    function schedule(redrawMarks) {
      if (redrawMarks) pendingMarks = true;
      if (raf) return;
      raf = requestAnimationFrame(function () {
        raf = null;
        commit(pendingMarks);
        pendingMarks = false;
      });
    }

    function commit(redrawMarks) {
      // Zooming most of the way back out abandons the focused district. Without
      // this the district you clicked stays expanded behind every badge, which
      // reads as a rendering bug rather than as state.
      // Zooming most of the way back out drops one level, not all of them.
      if (_focus.d && V.w > home.w * 0.35) { _focus.d = null; redrawMarks = true; }
      else if (_focus.c && !_focus.d && V.w > home.w * 0.7) { _focus.c = null; redrawMarks = true; }
      sv.setAttribute('viewBox', V.x + ' ' + V.y + ' ' + V.w + ' ' + V.h);
      _mapV = { x: V.x, y: V.y, w: V.w, h: V.h };
      var mpp = V.w / width();
      // Before anything reads the choropleth: the hatch tiles are sized in
      // metres, so they have to be re-cut whenever the scale moves.
      sizeHatch(mpp);
      // Which districts are open depends on the viewport, not just the scale, so
      // a pan can change the answer: redraw when the detail band or the focus
      // changes, and whenever a pan has moved far enough to bring a new district
      // into view.
      var detail = V.w < DETAIL_W;
      // Quantised to a third of the viewport so a drag costs at most a couple of
      // mark rebuilds, not one per frame -- rebuilding mid-drag is exactly what
      // used to make panning stutter.
      var pq = V.w / 3;
      var panKey = detail ? Math.round(V.x / pq) + ':' + Math.round(V.y / pq) : '';
      if (redrawMarks || lastMarkMpp === null || detail !== lastDetail ||
          panKey !== lastPanKey || focusKey() !== lastFocus ||
          Math.abs(Math.log(mpp / lastMarkMpp)) > 0.18) {
        lastMarkMpp = mpp;
        lastDetail = detail;
        lastPanKey = panKey;
        lastFocus = focusKey();
        marksG = document.getElementById('hs-marks');
        if (marksG) marksG.innerHTML = marksHtml(mpp, V);
        var exG = document.getElementById('hs-excl');
        if (exG) exG.innerHTML = exclHtml(mpp, V);
        // A district drawn as a label already carries its own name. Leaving the
        // standalone one up as well prints the name twice in two different
        // places, because the mark sits on the centre of the BUILDINGS and the
        // standalone label on the centre of the polygon. Districts with nothing
        // to count keep theirs -- that is the only name they get.
        var dls = sv.querySelectorAll('.hs-dlabel');
        for (var d2 = 0; d2 < dls.length; d2++) {
          var dk2 = dls[d2].getAttribute('data-dk');
          // At county level every one of these would be a 365-name pile-up on
          // top of 22 county marks, so the layer only exists inside a county.
          var show = _level > 0 && dk2.split('|')[0] === _focus.c && !_labelKeys[dk2];
          dls[d2].style.display = show ? '' : 'none';
        }
        // The choropleth follows the LEVEL. At national zoom a polygon is
        // coloured by its COUNTY's median, so 22 areas of colour answer the
        // question the reader is actually asking; only once a county is open
        // does each district get its own value. Attribute work on 730 nodes,
        // and only when the level or the focus changes -- never per frame.
        // Colour only what the rest of the page is willing to RANK.
        //
        // 嘉義縣's median is the highest in the country and rests on 18
        // buildings, so it was painted the darkest thing on the map — the
        // strongest visual claim the page makes, asserting exactly what the page
        // spends two thousand words refuting, from a sample the ranking chart
        // refuses to list. Anything under the same floor is now neutral.
        var FLOOR = (D.meta && D.meta.min_district_n) || 25;
        var cmed = {}, dmed = {};
        countyGroups().forEach(function (g) {
          if (g.n >= FLOOR) cmed[g.key] = yieldFillAt(g.med, 0);
        });
        districtGroups().forEach(function (g) {
          if (g.n >= FLOOR) dmed[g.key] = yieldFillAt(g.med, 1);
        });
        // National zoom shows whole counties; opening one reveals its districts.
        var cl = document.getElementById('hs-counties');
        if (cl) cl.style.display = _level === 0 ? '' : 'none';
        var dl0 = sv.querySelectorAll('.hs-land, .hs-bounds');
        for (var q0 = 0; q0 < dl0.length; q0++) {
          dl0[q0].style.display = _level === 0 ? 'none' : '';
        }
        var cps = sv.querySelectorAll('.hs-cland');
        for (var q1 = 0; q1 < cps.length; q1++) {
          var ck = cps[q1].getAttribute('data-dkey');
          if (cmed[ck]) cps[q1].setAttribute('fill', cmed[ck]);
        }
        var shapes = sv.querySelectorAll('.hs-land, .hs-bound');
        for (var s2 = 0; s2 < shapes.length; s2++) {
          var el = shapes[s2], sk = el.getAttribute('data-dkey');
          var cty = sk.split('|')[0];
          el.classList.toggle('foc', !!_focus.d && sk === _focus.d);
          el.classList.toggle('dim', !!_focus.c && cty !== _focus.c);
          if (el.classList.contains('hs-land')) {
            // At county level a city is ONE block, so even a district with no
            // pairs takes its county's colour -- painting the gaps grey is what
            // made 臺南市 look like a mosaic. Inside an open county the truth is
            // the other way round: a district with nothing matched is grey,
            // because that is what it has.
            var f = _level === 0 ? cmed[cty] : dmed[sk];
            el.classList.toggle('nodata', !f);
            // Bare paper, not a grey. "Nothing to measure" and "measured low"
            // have to be different marks, and against a map where every
            // measured area is hatched, no texture at all is the clearest way
            // to say it. The boundary still draws, so the district is an
            // outlined empty area rather than a hole in the picture.
            el.setAttribute('fill', f || 'none');
          }
        }
        // The legend describes the level actually on screen: at national zoom the
        // colour is a COUNTY median, inside a county a DISTRICT median, and
        // inside a district an individual building. Saying "報酬率" for all three
        // let a reader compare a county against a building and think the map had
        // told them something.
        var hn = document.getElementById('hs-hint');
        if (hn) hn.textContent = S(_level === 0 ? 'hint0' : _level === 1 ? 'hint1' : 'hint2');
        var rl = document.getElementById('hs-ramplab');
        var rx = document.getElementById('hs-rampax');
        if (rl) rl.textContent = S(_level === 0 ? 'rampLegC'
                                 : _level === 1 ? 'rampLegD' : 'rampLegB');
        if (rx) {
          var R = rampDomain(_level === 2 ? 2 : _level);
          rx.innerHTML = '<span>' + R[0].toFixed(1) + '%</span><span>' +
            R[1].toFixed(1) + '%</span>';
        }
        var bk = document.getElementById('hs-mapback');
        if (bk) {
          if (_focus.c) {
            var lbl = '', gs2, k2, fgNp = -1, fgN = -1;
            if (_focus.d) {
              gs2 = allDistricts(_focus.c);
              for (k2 = 0; k2 < gs2.length; k2++) if (gs2[k2].key === _focus.d) {
                lbl = '<b>' + esc(gs2[k2].district) + '</b> &middot; ' +
                  n0(gs2[k2].n) + ' ' + esc(S('mapClust'));
                fgNp = gs2[k2].np; fgN = gs2[k2].n;
              }
            } else {
              gs2 = countyGroups();
              for (k2 = 0; k2 < gs2.length; k2++) if (gs2[k2].key === _focus.c) {
                lbl = '<b>' + esc(gs2[k2].district) + '</b> &middot; ' +
                  n0(gs2[k2].n) + ' ' + esc(S('mapClust'));
                fgNp = gs2[k2].np; fgN = gs2[k2].n;
              }
            }
            // An area can have buildings and no way to draw them: five counties
            // have an address-point file and seventeen do not. Opening 西屯區
            // and seeing "122 棟" over an empty map reads as a broken map unless
            // the map says which of the two it is.
            // Two different empties, and conflating them is a lie: 茂林區 has
            // no matched pair at all, while 西屯區 has 122 and no coordinate
            // file to draw them with.
            // "← 板橋區" reads as "go to 板橋區" in every convention there is —
            // an iOS back bar, a breadcrumb — and 板橋區 is where the reader
            // already IS. The button now names its DESTINATION and the place
            // you are in sits beside it, not behind the arrow.
            var dest = _focus.d ? Sf('backTo', countyName(_focus.c)) : S('backHome');
            var note = fgN === 0 ? Sf('noPairsB')
              : (fgNp === 0 ? Sf('noCoordsB', n0(fgN) + ' ' + S('mapClust')) : null);
            bk.innerHTML = '<b class="hs-pillgo">' + esc(dest) + '</b>' +
              '<span class="hs-pillat">' + lbl + '</span>' +
              (note ? '<i>' + esc(note) + '</i>' : '');
            bk.removeAttribute('hidden');
          } else {
            bk.setAttribute('hidden', '');
          }
        }
      }
      // Stroke widths in metres. See the note in housing.css: non-scaling-stroke
      // is correct-looking and unusably slow on paths this size.
      //
      // These numbers are effectively PIXELS -- each is multiplied by mpp, which
      // is metres per pixel -- and they were retuned the day the widths first
      // took effect at all. The ordering is the point: the district boundary is
      // the heaviest line on the map, because separating districts is what the
      // map is for, and the streets are texture underneath it.
      var STROKES = [['.hs-rd1 path', 0.9], ['.hs-rd2 path', 0.5], ['.hs-mrt path', 0.9],
                     ['.hs-river path', 1.6], ['.hs-land', 3.4], ['.hs-bound', 1.8],
                     ['.hs-cland', 3.4], ['.hs-cbound', 2.0], ['.hs-dlabel', 2.6],
                     ['.hs-stn', 1.1], ['.hs-dcount', 3.0], ['.hs-dgname', 2.8],
                     ['.hs-dgnum', 2.6], ['.hs-ex', 0.55]];
      for (var t2 = 0; t2 < STROKES.length; t2++) {
        var els = sv.querySelectorAll(STROKES[t2][0]);
        for (var u = 0; u < els.length; u++) {
          els[u].setAttribute('stroke-width', STROKES[t2][1] * mpp);
        }
      }
      // The basemap is STAGED BY ZOOM.
      //
      // At full extent the map is answering "which district", and every street,
      // stream and metro line drawn across it is answering a question nobody has
      // asked yet. Thirty-three numbers over a spider's web of veins is what the
      // map looked like before this: four layers of context competing with the
      // one layer of content. Context now fades in as the reader arrives at the
      // scale where it starts to mean something -- rivers and arterials first,
      // then side streets, then stations, then their names.
      //
      // Home is ~65 km wide, so nothing here is on until roughly a 2x zoom.
      var STAGE = [['.hs-water', 30000], ['.hs-river', 30000], ['.hs-rd1', 30000],
                   ['.hs-mrt', 30000], ['.hs-rd2', 13000]];
      for (var v = 0; v < STAGE.length; v++) {
        var lay = sv.querySelector(STAGE[v][0]);
        if (lay) lay.style.display = V.w < STAGE[v][1] ? '' : 'none';
      }
      // Small, fixed-count layers: 131 stations + 131 names + 41 district names.
      var stnOn = V.w < 16000;
      var stn = sv.querySelectorAll('.hs-stn');
      for (var i = 0; i < stn.length; i++) {
        stn[i].style.display = stnOn ? '' : 'none';
        if (stnOn) stn[i].setAttribute('r', 2.6 * mpp);
      }
      var dl = sv.querySelectorAll('.hs-dlabel');
      for (var j = 0; j < dl.length; j++) dl[j].setAttribute('font-size', 12 * mpp);
      // Station NAMES come in later than the stations themselves: 131 of them at
      // once is a second label layer arguing with the district names.
      var zoomed = V.w < 7000;
      var sl = sv.querySelectorAll('.hs-stnlab');
      for (var q = 0; q < sl.length; q++) {
        sl[q].style.display = zoomed ? '' : 'none';
        if (zoomed) {
          sl[q].setAttribute('font-size', 11 * mpp);
          sl[q].setAttribute('dy', -4.5 * mpp);
        }
      }
      // The density grid is the coverage argument -- every building that sold,
      // against the few that can be priced. That argument is only legible at
      // city scale. Zoomed to one district its 400 m cells become a grey
      // checkerboard the size of city blocks, and it buries the buildings the
      // reader just asked to see.
      var dens = sv.querySelector('.hs-dens');
      if (dens) dens.style.display = V.w < 20000 ? 'none' : '';
      scaleBar(mpp);
    }

    function scaleBar(mpp) {
      var el = document.getElementById('hs-scale');
      if (!el) return;
      var target = 110 * mpp;
      var pow = Math.pow(10, Math.floor(Math.log(target) / Math.LN10));
      var nice = [1, 2, 5, 10].map(function (m) { return m * pow; })
        .reduce(function (a, b) { return Math.abs(b - target) < Math.abs(a - target) ? b : a; });
      el.querySelector('i').style.width = (nice / mpp).toFixed(0) + 'px';
      el.querySelector('span').textContent = nice >= 1000 ? (nice / 1000) + ' km' : nice + ' m';
    }

    function clamp() {
      var mx = home.w * 0.4, my = home.h * 0.4;
      V.x = Math.min(Math.max(V.x, home.x - mx), home.x + home.w + mx - V.w);
      V.y = Math.min(Math.max(V.y, home.y - my), home.y + home.h + my - V.h);
    }
    function zoomAt(factor, cx, cy) {
      var nw = Math.min(home.w, Math.max(600, V.w * factor));
      var k = nw / V.w;
      V.x = cx - (cx - V.x) * k;
      V.y = cy - (cy - V.y) * k;
      V.w = nw; V.h = V.h * k;
      clamp(); schedule(false);
    }
    function toWorld(cx, cy) {
      var r = sv.getBoundingClientRect();
      return { x: V.x + (cx - r.left) / r.width * V.w,
               y: V.y + (cy - r.top) / r.height * V.h };
    }

    host.addEventListener('wheel', function (e) {
      e.preventDefault();
      var p = toWorld(e.clientX, e.clientY);
      var d = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
      zoomAt(Math.exp(Math.max(-90, Math.min(90, d)) * 0.0016), p.x, p.y);
    }, { passive: false });

    // Pointer events, not mouse events: the map had NO touch handling at all,
    // which on a phone means it cannot be panned or zoomed. One code path now
    // covers mouse, trackpad, pen and touch, and two pointers give pinch.
    var pts = {}, panStart = null, pinchStart = null, moved = false;

    function pointerCount() { return Object.keys(pts).length; }

    // Pointer capture is taken LAZILY, once a drag is actually under way.
    // Capturing on pointerdown retargets pointerup AND the click to the <svg>
    // itself, so e.target.closest('.hs-dg' / '.hs-mdot' / '.hs-land') found
    // nothing and every click on the map was silently dead -- badges, buildings
    // and districts alike. Capture is only needed to keep receiving moves after
    // the pointer leaves the element, which cannot happen before it has moved.
    function grab(id) { try { sv.setPointerCapture(id); } catch (x) {} }

    sv.addEventListener('pointerdown', function (e) {
      pts[e.pointerId] = { x: e.clientX, y: e.clientY };
      moved = false;
      if (pointerCount() === 1) {
        panStart = { p: toWorld(e.clientX, e.clientY), vx: V.x, vy: V.y,
                     cx: e.clientX, cy: e.clientY };
        sv.classList.add('dragging');
      } else if (pointerCount() === 2) {
        var k = Object.keys(pts);
        var a = pts[k[0]], b2 = pts[k[1]];
        pinchStart = {
          dist: Math.hypot(a.x - b2.x, a.y - b2.y),
          w: V.w,
          mid: toWorld((a.x + b2.x) / 2, (a.y + b2.y) / 2)
        };
        for (var z = 0; z < k.length; z++) grab(+k[z]);
        panStart = null;
      }
    });

    sv.addEventListener('pointermove', function (e) {
      if (pts[e.pointerId]) { pts[e.pointerId].x = e.clientX; pts[e.pointerId].y = e.clientY; }

      if (pinchStart && pointerCount() === 2) {
        var k = Object.keys(pts), a = pts[k[0]], b2 = pts[k[1]];
        var d = Math.hypot(a.x - b2.x, a.y - b2.y);
        if (d > 4) {
          var target = Math.min(home.w, Math.max(600, pinchStart.w * (pinchStart.dist / d)));
          var kk = target / V.w;
          V.x = pinchStart.mid.x - (pinchStart.mid.x - V.x) * kk;
          V.y = pinchStart.mid.y - (pinchStart.mid.y - V.y) * kk;
          V.w = target; V.h = V.h * kk;
          clamp(); schedule(false);
        }
        moved = true;
        return;
      }

      if (panStart) {
        // A tap is not a drag. Without a slack radius the tiniest tremor between
        // pointerdown and pointerup set moved=true and the click handler bailed.
        if (!moved) {
          if (Math.abs(e.clientX - panStart.cx) < 4 &&
              Math.abs(e.clientY - panStart.cy) < 4) return;
          grab(e.pointerId);
        }
        var r = sv.getBoundingClientRect();
        V.x = panStart.vx - (e.clientX - r.left) / r.width * V.w + (panStart.p.x - panStart.vx);
        V.y = panStart.vy - (e.clientY - r.top) / r.height * V.h + (panStart.p.y - panStart.vy);
        moved = true; clamp();
        // Pan never re-clusters: membership does not change when the scale is
        // unchanged, and rebuilding marks mid-drag is what made it stutter.
        schedule(false);
        return tipHide();
      }

      if (e.pointerType === 'touch') return;   // no hover on touch
      hover(e);
    });

    function endPointer(e) {
      delete pts[e.pointerId];
      if (pointerCount() < 2) pinchStart = null;
      if (pointerCount() === 0) { panStart = null; sv.classList.remove('dragging'); }
    }
    sv.addEventListener('pointerup', endPointer);
    sv.addEventListener('pointercancel', endPointer);
    sv.addEventListener('pointerleave', function (e) { endPointer(e); tipHide(); });

    function hover(e) {
      var dg = e.target.closest('.hs-dg');
      if (dg) {
        return tipShow('<b>' + esc(dg.getAttribute('data-dname')) + '</b>' +
          kv(S('mapNBld'), dg.getAttribute('data-n') + ' ' + S('mapClust')) +
          kv(S('thYield'), dg.getAttribute('data-med')
            ? dg.getAttribute('data-med') + '%' : '\u2014') +
          '<div class="k" style="margin-top:3px">' + esc(S('mapClickDist')) + '</div>',
          e.clientX, e.clientY);
      }
      var mk = e.target.closest('.hs-mdot');
      if (!mk) return tipHide();
      var hit = buildingByAddr(mk.getAttribute('data-b'));
      if (!hit) return tipHide();
      var ny = netYield(hit);
      tipShow('<b>' + esc(hit.a) + '</b>' + kv(S('thType'), typeLabel(hit.t)) +
        kv(S('thYield'), pct(hit.y)) + kv(S('thNet'), ny == null ? '--' : pct(ny)) +
        kv(S('thPrice'), money(hit.p)), e.clientX, e.clientY);
    }

    sv.addEventListener('dblclick', function (e) {
      var p = toWorld(e.clientX, e.clientY);
      zoomAt(1 / 2.2, p.x, p.y);
    });

    function flyTo(g) {
      var nv = districtView(g);
      V.x = nv.x; V.y = nv.y; V.w = nv.w; V.h = nv.h;
      clamp();
      schedule(true);
    }

    function focusCounty(c) {
      var gs = countyGroups();
      for (var i = 0; i < gs.length; i++) if (gs[i].key === c) {
        _focus = { c: c, d: null };
        return flyTo(gs[i]);
      }
    }

    function focusDistrict(key) {
      var c = key.split('|')[0];
      // allDistricts, not districtGroups: an empty district is still a place a
      // reader can ask to look at, and bouncing them back to the county reads
      // as a dead click.
      var gs = allDistricts(c);
      for (var i = 0; i < gs.length; i++) if (gs[i].key === key) {
        _focus = { c: c, d: key };
        return flyTo(gs[i]);
      }
      focusCounty(c);
    }

    // One click always means "go one level deeper into what I clicked".
    function drillTo(key) {
      if (!key) return;
      if (key.indexOf('|') < 0) return focusCounty(key);
      if (_focus.c === key.split('|')[0]) return focusDistrict(key);
      return focusCounty(key.split('|')[0]);
    }

    sv.addEventListener('click', function (e) {
      if (moved) { moved = false; return; }
      var dg = e.target.closest('.hs-dg');
      if (dg) return drillTo(dg.getAttribute('data-key'));
      var mk = e.target.closest('.hs-mdot');
      if (mk) return openPanel(buildingByAddr(mk.getAttribute('data-b')));
      // Clicking anywhere in a shape does what clicking its mark does. Two
      // different meanings for two parts of the same shape is not a distinction
      // a reader can be expected to discover.
      var t = e.target.closest('.hs-land');
      if (t) return drillTo(t.getAttribute('data-dkey'));
    });

    // Everything the mouse can do, from the keyboard.
    //
    // Enter/Space on a focused mark drills exactly as a click does; Escape steps
    // back out a level; arrows pan by a tenth of the view; +/- zoom about the
    // CENTRE (the wheel zooms to the cursor, which a keyboard has none of); Home
    // returns to the country. Without this the map was reachable only by typing
    // a name you already knew into the search box.
    sv.addEventListener('keydown', function (e) {
      var t = e.target;
      var dg = t && t.closest && t.closest('.hs-dg');
      var mk = t && t.closest && t.closest('.hs-mdot');
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        if (dg) { e.preventDefault(); return drillTo(dg.getAttribute('data-key')); }
        if (mk) { e.preventDefault(); return openPanel(buildingByAddr(mk.getAttribute('data-b'))); }
        return;
      }
      // Innermost thing first: with a building open, Escape means "close this",
      // not "zoom out". closePanel returns false when there was nothing to
      // close, which is what lets one key do both jobs in the right order.
      if (e.key === 'Escape') {
        e.preventDefault();
        if (closePanel()) return;
        return popFocus();
      }
      if (e.key === 'Home') { e.preventDefault(); return goHome(); }
      if (e.key === '+' || e.key === '=') {
        e.preventDefault(); return zoomAt(1 / 1.6, V.x + V.w / 2, V.y + V.h / 2);
      }
      if (e.key === '-' || e.key === '_') {
        e.preventDefault(); return zoomAt(1.6, V.x + V.w / 2, V.y + V.h / 2);
      }
      var dx = 0, dy = 0, step = V.w * 0.1;
      if (e.key === 'ArrowLeft') dx = -step;
      else if (e.key === 'ArrowRight') dx = step;
      // World y grows north, and V.y lives in the flipped frame, so Up is +.
      else if (e.key === 'ArrowUp') dy = -step;
      else if (e.key === 'ArrowDown') dy = step;
      else return;
      e.preventDefault();
      V.x += dx; V.y += dy;
      clamp(); schedule(false);
    });

    // The tooltip is the only place a median is written down, and it was bound
    // to pointermove alone -- unreachable by keyboard, and explicitly skipped
    // for touch. Focus now shows the same card.
    sv.addEventListener('focusin', function (e) {
      var el = e.target && e.target.closest && e.target.closest('.hs-dg, .hs-mdot');
      if (!el) return;
      var r = el.getBoundingClientRect();
      hover({ target: el, clientX: r.left + r.width / 2, clientY: r.top });
    });
    sv.addEventListener('focusout', tipHide);

    function goHome() {
      _focus = { c: null, d: null };
      V.x = home.x; V.y = home.y; V.w = home.w; V.h = home.h;
      schedule(true);
    }

    // The pill walks BACK one level, because that is the move a reader wants
    // after drilling in: district -> its county -> the country.
    function popFocus() {
      if (_focus.d) {
        var c = _focus.c;
        _focus = { c: c, d: null };
        var gs = countyGroups();
        for (var i = 0; i < gs.length; i++) if (gs[i].key === c) return flyTo(gs[i]);
        return schedule(true);
      }
      goHome();
    }

    // ── search box ──
    var q = document.getElementById('hs-msq');
    var res = document.getElementById('hs-msres');
    var hits = [];

    function drawResults() {
      if (!res) return;
      if (!hits.length) { res.setAttribute('hidden', ''); res.innerHTML = ''; return; }
      res.innerHTML = hits.map(function (r, i) {
        return '<li><button type="button" data-i="' + i + '">' +
          '<span class="l">' + esc(r.label) + '</span>' +
          '<span class="s">' + esc(r.sub || (n0(r.n) + ' ' + S('msBld'))) + '</span>' +
        '</button></li>';
      }).join('');
      res.removeAttribute('hidden');
    }

    function pick(r) {
      if (!r) return;
      if (q) { q.value = ''; }
      hits = []; drawResults();
      if (r.kind === 'county') return focusCounty(r.key);
      if (r.kind === 'district') return focusDistrict(r.key);
      // A building: open the district it sits in, then its panel. Flying to a
      // single dot with no context around it is a worse answer than showing the
      // street it is on.
      var b = buildingByAddr(r.key);
      if (!b) return;
      focusDistrict(b.c + '|' + b.d);
      openPanel(b);
    }

    if (q) {
      q.addEventListener('input', function () {
        hits = mapSearch(q.value);
        drawResults();
      });
      q.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); pick(hits[0]); }
        if (e.key === 'Escape') { q.value = ''; hits = []; drawResults(); }
      });
    }
    if (res) {
      res.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-i]');
        if (btn) pick(hits[+btn.getAttribute('data-i')]);
      });
    }

    host.addEventListener('click', function (e) {
      if (e.target.closest('#hs-mapback')) return popFocus();
      var z = e.target.closest('[data-zoom]');
      if (!z) return;
      var k = z.getAttribute('data-zoom');
      if (k === 'home') {
        goHome();
      } else {
        zoomAt(k === 'in' ? 1 / 1.6 : 1.6, V.x + V.w / 2, V.y + V.h / 2);
      }
    });

    commit(true);
  }

  // Address -> building, memoised. The click and hover paths were each doing a
  // linear scan of 2,549 records.
  var _byAddr = null;
  function buildingByAddr(a) {
    if (!_byAddr) {
      _byAddr = {};
      for (var i = 0; i < D.buildings.length; i++) _byAddr[D.buildings[i].a] = D.buildings[i];
    }
    return _byAddr[a];
  }

  // ── detail panel ──────────────────────────────────────────────────────
  // Two levels, like the map.
  //
  // 59 district rows in one fixed-height chart is a 1,594 px column, and a
  // reader comparing 高雄 with 臺北 has to scroll past forty rows that are not
  // either of them. Counties rank first; opening one ranks its districts. Both
  // levels obey the same n >= MIN_DISTRICT_N floor, and both carry a bootstrap
  // CI rather than a bare dot.
  var _rankCounty = null;

  function secDistrict() {
    var atCounty = !_rankCounty;
    var ds = atCounty
      ? (D.counties || [])
      : (D.districts || []).filter(function (d) { return d.county === _rankCounty; });
    var cityName = '';
    if (!atCounty) {
      (D.counties || []).forEach(function (c) {
        if (c.county === _rankCounty) cityName = c.city;
      });
    }
    var W = chartW(860), rowH = 26, padT = 26;
    // On a phone the building count column goes (it is in the tooltip) and
    // the yield label takes its place at the right edge. With padR = 56 and
    // the label still anchored at W - 58, the three highest dots printed
    // straight through their own values.
    var narrow = W < 480;
    var padL = narrow ? 84 : 118, padR = narrow ? 62 : 104;
    var H = padT + ds.length * rowH + 34;
    var lo = 1.6, hi = 3.4;
    // The line shows the 95% CI on the median, not the interquartile spread of
    // buildings: the question this chart invites is "is district A above district
    // B", and only the CI can answer that. Falls back to the IQR if a district
    // has no bootstrap entry.
    ds.forEach(function (d) {
      var B = D.bootstrap || {};
      var ci = atCounty
        ? (B.county ? B.county[d.county] : null)
        : (B.district ? B.district[d.county + '|' + d.district] : null);
      d._lo = (ci && ci.lo != null) ? ci.lo : d.q1;
      d._hi = (ci && ci.hi != null) ? ci.hi : d.q3;
      lo = Math.min(lo, d._lo); hi = Math.max(hi, d._hi);
    });
    lo = Math.floor(lo * 2) / 2; hi = Math.ceil(hi * 2) / 2;
    var x = function (v) { return padL + (v - lo) / (hi - lo) * (W - padL - padR); };
    var grid = ticks(lo, hi, Math.round((hi - lo) * 2)).map(function (t) {
      return line(x(t), padT - 8, x(t), H - 30, 'var(--grid)', 1) +
        txt(x(t), H - 14, t.toFixed(1), 'hs-axis', 'middle',
            ' style="fill:var(--muted);font-size:11px"');
    }).join('');
    var rows = ds.map(function (d, i) {
      var dk = d.county + '|' + d.district;
      var y = padT + i * rowH + rowH / 2, on = !atCounty && state.district === dk;
      // At county level the row is a door, not a filter: data-rank opens it.
      var handle = atCounty ? ' data-rank="' + esc(d.county) + '"'
                            : ' data-d="' + esc(dk) + '"';
      return '<g class="hs-drow"' + handle + ' style="cursor:pointer">' +
        rect(0, y - rowH / 2, W, rowH, on ? 'var(--accent-soft)' : 'transparent') +
        txt(padL - 10, y + 4, d.district, 'hs-glab', 'end',
            ' style="font-weight:' + (on ? '650' : '400') + '"') +
        txt(6, y + 4, atCounty
              ? (LANG === 'zh' ? n0(d.districts) + ' 區' : d.districts + ' dist.')
              : (LANG === 'zh' ? d.city.slice(0, 3) : countyEn(d.county)),
            'hs-glab', 'start', ' style="fill:var(--subtle);font-size:11px"') +
        line(x(d._lo), y, x(d._hi), y, 'var(--dim)', 3, ' stroke-linecap="round"') +
        '<circle cx="' + x(d.yield) + '" cy="' + y + '" r="5" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>' +
        txt(narrow ? W - 4 : W - 58, y + 4, d.yield.toFixed(2) + '%', 'hs-vlab', 'end') +
        (narrow ? '' : txt(W - 4, y + 4, n0(d.buildings), 'hs-glab', 'end',
            ' style="fill:var(--subtle);font-size:11px"')) +
      '</g>';
    }).join('');
    return sec('distEy', 'distH', 0,
      '<p class="hs-prose">' + esc(Sf('distP', D.meta.min_district_n)) + '</p>' +
      '<div class="hs-controls">' +
        (atCounty
          ? '<span class="hs-mono-s">' + esc(S('rankInto')) + '</span>'
          : '<button class="hs-chip" data-rank="">' + esc(S('rankBack')) + '</button>' +
            '<b class="hs-rankwho">' + esc(cityName) + '</b>') +
        '<button class="hs-chip" data-dist="" aria-pressed="' + (!state.district) + '">' +
          esc(atCounty ? S('rankAllC') : S('distAll')) + '</button>' +
        (state.district ? '<button class="hs-chip" aria-pressed="true" data-dist="">&times; ' +
          esc(state.district.split('|')[1] || state.district) + '</button>' : '') +
      '</div>' +
      (ds.length
        ? '<div class="hs-card hs-scroll" id="hs-dist">' + svg(W, H, grid + rows, '', S('distH')) + '</div>'
        : '<p class="hs-prose hs-fig-n">' +
            esc(Sf('rankNone', cityName, D.meta.min_district_n)) + '</p>') +
      // "most of this ranking is not distinguishable" understated it: every
      // adjacent pair overlaps, 79 of 79. When that is the case say so, and
      // name the two ends that genuinely do separate.
      '<p class="hs-fig-n hs-prose">' + esc(ciNoteText(atCounty)) + '</p>' +
      (D.vacancy_breakeven && D.vacancy_breakeven.breakeven_vacancy_pct
        ? '<p class="hs-fig-n hs-prose">' + esc(Sf('vbNote',
            D.vacancy_breakeven.city, D.vacancy_breakeven.district,
            D.vacancy_breakeven.default_vacancy_pct,
            D.vacancy_breakeven.breakeven_vacancy_pct,
            D.vacancy_breakeven.city, countyLowUsePct(D.vacancy_breakeven.city),
            D.vacancy_breakeven.breakeven_vacancy_pct)) + '</p>' : ''));
  }

  // The ladder is a PATH, and for a long time it was captioned as a
  // measurement of what each cleaning decision is worth. That caption was
  // false, and the social-housing rung is where it showed: it read -0.17pp,
  // "remove subsidised leases and the yield FALLS", which is backwards for a
  // population renting 28% below market.
  //
  // Two things produced it, and neither was the filter:
  //   1. Mixed units. Rungs 1-5 were medians over PAIRS, 6-7 over BUILDINGS.
  //      Social leases concentrate in a handful of enormous 包租代管 studio
  //      towers, so a pair-level median weights those buildings 14:1 where a
  //      building-level median weights them 3.3:1. Every rung is now read in
  //      one unit -- the building -- and the sign comes back.
  //   2. Ordering. The social filter is applied while room-shares are still in
  //      the sample, and room-shares (yield ~1.3%, because their area field
  //      describes the building rather than the let) are 15% of market leases
  //      and 0% of social ones. Dropping social housing therefore TRIPLES the
  //      room-share weight, and the aggregate falls while every component
  //      rises. Textbook Simpson.
  //
  // So the ladder now shows the path, and `filter_marginals` shows the filters.
  // Both, side by side, or the page repeats the claim that the path IS the
  // measurement.
  function secLadder() {
    function val(r) { return r.yield_building != null ? r.yield_building : r.yield; }
    // The `building` rung used to be the ladder's last step, because rungs 1-5
    // were read per pair and it was the one that switched units. Now that every
    // rung carries both units it is a verbatim duplicate of `related`, so it is
    // not drawn -- the per-pair figure on EVERY row teaches the same lesson six
    // times instead of once. It stays in the payload; only the row is dropped.
    var shown = [];
    D.ladder.forEach(function (r, i) {
      if (r.key !== 'building') shown.push({ r: r, i: i });
    });
    var max = 0;
    shown.forEach(function (s) { max = Math.max(max, val(s.r)); });
    var rows = shown.map(function (s, j) {
      var r = s.r, v = val(r), d = j === 0 ? null : v - val(shown[j - 1].r);
      var cls = d == null ? '' : (d >= 0 ? 'up' : 'down');
      return '<button class="hs-rung" data-rung="' + s.i + '" type="button" aria-current="' +
        (j === shown.length - 1 ? 'true' : 'false') + '">' +
        '<span class="hs-rung-i">' + String(j + 1).padStart(2, '0') + '</span>' +
        '<span class="hs-rung-t">' + esc(LANG === 'zh' ? r.zh : r.en) +
          '<em>' + n0(r.buildings) + ' ' + esc(S('rungBldgs')) +
          (r.lo != null && r.hi != null
            ? ' · ' + esc(Sf('ci95', r.lo.toFixed(2), r.hi.toFixed(2))) : '') +
          (r.yield_pair != null
            ? ' · ' + esc(Sf('rungPer', r.yield_pair.toFixed(2), n0(r.pairs))) : '') +
          '</em></span>' +
        '<span class="hs-rung-v">' + v.toFixed(2) + '%</span>' +
        '<span class="hs-rung-d ' + cls + '">' +
          (d == null ? '&mdash;' : (d >= 0 ? '+' : '') + d.toFixed(2) + 'pp') +
          '<i>' + svg(46, 5, rect(0, 1, Math.round(v / max * 46), 4, 'url(#hxbar)')) + '</i></span>' +
      '</button>';
    }).join('');
    var h = D.headline;
    // shown.length, not D.ladder.length: the `building` rung is in the payload
    // and not drawn, so the heading said five over six rows.
    return sec('ladEy', null, 1,
      '<h2>' + esc(Sf('ladH', shown.length)) + '</h2>' +
      '<p class="hs-prose">' + esc(S('ladP')) + '</p>' +
      '<div class="hs-card"><div class="hs-ladder">' + rows + '</div></div>' +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('ladNote', D.concentration.top10_share,
          h.pair_level_yield.toFixed(2), h.yield.toFixed(2))) + '</p>' +
      ladMarginals() + parkingAudit());
  }

  // What each filter is worth on its own: the average marginal effect over all
  // six orderings (a Shapley value over the 2^3 grid). They sum exactly to the
  // total move, which is what makes this a decomposition and not three
  // unrelated sensitivities.
  function ladMarginals() {
    var m = D.filter_marginals;
    if (!m || !m.shapley || !m.shapley.building) return '';
    var KEYS = ['social', 'rooms', 'related'];
    var LABS = { social: 'fmSocial', rooms: 'fmRooms', related: 'fmRelated' };
    var rows = KEYS.map(function (k) {
      var sb = m.shapley.building[k], sp = m.shapley.pair[k], pa = m.path[k];
      if (sb == null) return '';
      return '<tr><td>' + esc(S(LABS[k])) + '</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' +
          (pa >= 0 ? '+' : '') + pa.toFixed(3) + 'pp</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' +
          (sp >= 0 ? '+' : '') + sp.toFixed(3) + 'pp</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums;font-weight:600">' +
          (sb >= 0 ? '+' : '') + sb.toFixed(3) + 'pp</td></tr>';
    }).join('');
    var mech = D.marginal_mechanism || {};
    var con = mech.concentration;
    var byType = (mech.by_let_type || []).map(function (t) {
      return '<tr><td>' + esc(t.let_type) + '</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' +
          t.social.toFixed(2) + '%</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' +
          t.market.toFixed(2) + '%</td>' +
        '<td style="text-align:right;font-variant-numeric:tabular-nums">' +
          t.social_share_pct.toFixed(1) + '% / ' + t.market_share_pct.toFixed(1) + '%</td></tr>';
    }).join('');
    return '<div class="hs-fig" style="margin-top:var(--sp7)">' +
        '<div class="hs-fig-t">' + esc(S('fmH')) + '</div>' +
        '<p class="hs-prose">' + esc(S('fmP')) + '</p>' +
        '<div class="hs-scroll"><table style="font-size:13.5px" aria-label="' + esc(S('fmH')) + '"><thead><tr>' +
          '<th style="cursor:default"></th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmPath')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmShapPair')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmShapBldg')) + '</th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
        '<p class="hs-plain">' + esc(S('fmWhy')) + '</p>' +
        (byType ? '<div class="hs-scroll" style="margin-top:var(--sp5)">' +
          '<table style="font-size:13.5px" aria-label="' + esc(S('fmLet')) + ' × ' + esc(S('fmSoc')) + '／' + esc(S('fmMkt')) + '"><thead><tr>' +
          '<th style="cursor:default">' + esc(S('fmLet')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmSoc')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmMkt')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('fmMix')) + '</th>' +
          '</tr></thead><tbody>' + byType + '</tbody></table></div>' : '') +
        (con ? '<p class="hs-fig-n hs-prose">' + esc(Sf('fmConc',
            con.with_social.pairs_per_building.toFixed(1),
            con.without.pairs_per_building.toFixed(1),
            con.pair_weight_ratio.toFixed(1),
            con.bldg_weight_ratio.toFixed(1))) + '</p>' : '') +
      '</div>';
  }

  function secBias() {
    var rb = D.rent_bias;
    if (!rb || !rb.market || !rb.market.rent_ping) return '';
    var W = chartW(560), H = 120, padL = 110, barH = 34;
    var mx = Math.max(rb.social.rent_ping, rb.market.rent_ping);
    // Market vs social housing. Both were ink once the palette collapsed, so
    // they separate by texture: the market bar is hatched, the social one is
    // an empty outline. Same solid/hollow grammar as the cost waterfall.
    var items = [[S('biasMkt'), rb.market, 'url(#hxbar)'],
                 [S('biasSoc'), rb.social, 'none']];
    var bars = items.map(function (it, i) {
      var y = 16 + i * (barH + 20), w = it[1].rent_ping / mx * (W - padL - 130);
      return txt(padL - 12, y + barH / 2 + 4, it[0], 'hs-glab', 'end') +
        rect(padL, y, w, barH, it[2],
             ' stroke="var(--text)" stroke-width="1.1"') +
        txt(padL + w + 10, y + barH / 2 + 5, n0(it[1].rent_ping) + ' ' + S('biasUnit'), 'hs-vlab', 'start') +
        txt(padL + w + 10, y + barH / 2 + 19, 'n=' + n0(it[1].n), 'hs-glab', 'start',
            ' style="fill:var(--subtle);font-size:10.5px"');
    }).join('');
    return sec('biasEy', null, 1,
      '<h2>' + esc(Sf('biasH', rb.social_share_pct)) + '</h2>' +
      '<p class="hs-prose lede">' + esc(Sf('biasP', Math.abs(rb.gap_pct))) + '</p>' +
      '<div class="hs-card hs-scroll">' + svg(W, H, bars, '', Sf('biasH', D.rent_bias.social_share_pct.toFixed(1))) + '</div>');
  }


  // A stated assumption in the cleaning, tested within building, at the foot
  // of the honesty ladder where the cleaning decisions live. Not a rung of
  // D.ladder (the last rung must stay the headline); two bounds beside it.
  function parkingAudit() {
    var pa = D.parking_audit;
    if (!pa || !pa.treatments || pa.treatments.length !== 3 || !pa.verdict) return '';
    var T = {}; pa.treatments.forEach(function (t) { T[t.case] = t; });
    var A = T.area_only, Bd = T.drop, C = T.impute, V = pa.verdict, W = pa.within_building || {};
    if (!A || !Bd || !C) return '';
    var P = W.total_unpriced_vs_priced || {}, sh = pa.share || {}, ex = pa.exposure || {}, lets = pa.lets || {};
    var s100 = (sh.park_rent_share_median * 100).toFixed(1);
    var vkey = V.verdict === 'assumption_fails' ? 'pkaVerdictFails' : V.verdict === 'assumption_holds' ? 'pkaVerdictHolds' : 'pkaVerdictInc';
    var f2 = function (v) { return v == null ? '--' : v.toFixed(2); };
    var pctd = function (r) { return r == null ? '--' : ((r - 1) * 100).toFixed(1); };
    // one token per comparison, ordered per language: 「高 14.7%」 / "14.7% more"
    var dirPct = function (r) { return r == null ? '--' : Sf(r >= 1 ? 'pkaMore' : 'pkaLess', Math.abs((r - 1) * 100).toFixed(1)); };
    var sgn = function (r) { return r == null ? '--' : (r >= 1 ? '+' : '') + ((r - 1) * 100).toFixed(1); };

    // the within-building table, predictions beside the observation
    var s = sh.park_rent_share_median || 0;
    var trow = function (label, r, ifH, ifF) {
      if (!r || !r.n) return '';
      return '<tr><td>' + esc(label) + '</td><td class="num">' + n0(r.n) + '</td><td class="num">' + f2(r.median) + '</td>' +
        '<td class="num">' + (r.lo == null ? '--' : f2(r.lo) + '–' + f2(r.hi)) + '</td>' +
        '<td class="num">' + f2(r.q1) + '–' + f2(r.q3) + '</td><td class="num">' + ifH + '</td><td class="num">' + ifF + '</td></tr>';
    };
    var ctl = W.dwell_priced_vs_nopark || {};
    var table = '<div class="hs-scroll"><table aria-label="' + esc(S('pkaTblCap')) + '" style="font-size:13.5px"><thead><tr><th></th>' +
      '<th class="num">' + esc(S('pkThN')) + '</th><th class="num">' + esc(S('thRatio')) + '</th><th class="num">95% CI</th><th class="num">' + esc(S('thIqr')) + '</th>' +
      '<th class="num">' + esc(S('thIfHolds')) + '</th><th class="num">' + esc(S('thIfFails')) + '</th></tr></thead><tbody>' +
      trow(S('pkaRow1'), P, f2(1 - s), '1.00') +
      trow(S('pkaRow1a'), W.total_unpriced_area_itemised_vs_priced, f2(1 - s), '1.00') +
      trow(S('pkaRow1b'), W.total_unpriced_nothing_itemised_vs_priced, f2(1 - s), '1.00') +
      trow(S('pkaRow2'), W.dwell_unpriced_vs_priced, '1.00', f2(1 / (1 - s))) +
      trow(S('pkaRow3'), W.dwell_unpriced_vs_nopark, ctl.median == null ? '--' : f2(ctl.median), ctl.median == null ? '--' : f2(ctl.median / (1 - s))) +
      trow(S('pkaRow4'), ctl, '—', '—') +
      '</tbody></table></div><p class="hs-fig-n">' + esc(S('pkaTblCap')) + '</p>';
    var W2 = W.dwell_unpriced_vs_priced || {}, W3 = W.dwell_unpriced_vs_nopark || {};
    var corr = (W2.n && W3.n && ctl.n) ? '<p class="hs-prose">' + esc(Sf('pkaCorr',
      dirPct(W2.median), n0(W2.n), sgn(W2.lo), sgn(W2.hi), ((1 / (1 - s) - 1) * 100).toFixed(1),
      dirPct(W3.median), n0(W3.n), sgn(W3.lo), sgn(W3.hi),
      dirPct(ctl.median), n0(ctl.n), sgn(ctl.lo), sgn(ctl.hi))) + '</p>' : '';
    var who = lets.priced_by_service ? '<p class="hs-fig-n hs-prose">' + esc(Sf('pkaWho', n0(lets.priced),
      Object.keys(lets.priced_by_service).map(function (k) { return k + ' ' + n0(lets.priced_by_service[k]); }).join('、'))) + '</p>' : '';
    var soc = pa.social_only && pa.social_only.total_unpriced_vs_priced;
    var socP = soc && soc.n ? '<p class="hs-fig-n hs-prose">' + esc(Sf('pkaSocial', n0(soc.n), f2(soc.median), f2(soc.lo), f2(soc.hi), s100)) + '</p>' : '';

    // three cards: gross big, net + buildings + CI beneath
    function card(t, label, muted) {
      return '<div class="hs-vs-item' + (muted ? ' muted' : '') + '"><div class="hs-vs-v">' + t.gross.toFixed(2) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) + '<br><span class="hs-sub2">' + esc(Sf('pkaNet', t.net.toFixed(2))) + ' · ' + n0(t.buildings) + ' ' + esc(S('rungBldgs')) +
        (muted ? ' · ' + (t.gross_delta_pp >= 0 ? '+' : '') + t.gross_delta_pp.toFixed(3) + 'pp' : '') + '</span>' +
        (t.gross_lo == null ? '' : '<br><span class="hs-sub2">' + esc(Sf('ci95', t.gross_lo.toFixed(2), t.gross_hi.toFixed(2))) + '</span>') + '</div></div>';
    }
    var src = C.source_split || {};
    var cards = '<div class="hs-vs" style="max-width:720px">' + card(C, S('pkaC'), false) + card(A, S('pkaA'), true) + card(Bd, S('pkaB'), true) + '</div>' +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('pkaImpRule', n0(src.building), n0(C.min_county_n), n0(src.county), n0(C.national_median_ntd), n0(src.national),
        n0(C.imputed_median_ntd), n0(C.dropped_under_floor))) + '</p>';

    // exposure + county table (pairs only: one denominator per row)
    var expo = '<p class="hs-prose">' + esc(Sf('pkaExpo', n0(lets.unpriced), n0(lets.clean), (lets.unpriced_pct || 0).toFixed(1), (lets.unpriced_of_bundled_pct || 0).toFixed(1),
      n0(ex.pairs_total), n0(ex.pairs_on_unpriced), (ex.pairs_on_unpriced_pct || 0).toFixed(1), n0(ex.buildings_total), n0(ex.buildings_any_unpriced),
      (ex.buildings_any_unpriced_pct || 0).toFixed(1), n0(ex.buildings_only_unpriced), (ex.buildings_only_unpriced_pct || 0).toFixed(1))) + '</p>' +
      ((ex.by_county || []).length ? '<div class="hs-scroll"><table aria-label="' + esc(S('pkaThUnp')) + '" style="font-size:13.5px"><thead><tr><th></th><th class="num">' + esc(S('pkaThPairs')) + '</th><th class="num">' + esc(S('pkaThUnp')) + '</th><th class="num">%</th></tr></thead><tbody>' +
        ex.by_county.map(function (r) { return '<tr><td>' + esc(countyName(r.county)) + '</td><td class="num">' + n0(r.pairs) + '</td><td class="num">' + n0(r.unpriced) + '</td><td class="num">' + r.pct.toFixed(1) + '%</td></tr>'; }).join('') +
        '</tbody></table></div>' : '');

    // coverage line: horizontal bars, so chartW applies
    var cov = pa.coverage || {};
    var W_ = 520, padL = 168, RH = 30, H = 12 + 3 * RH, PW = W_ - padL - 60;   // natural width, pans on a phone
    var mx = Math.max(cov.impute || 1, 1);
    var body = [[S('pkaCovOld'), cov.parking_drop_rung, 'url(#hxbarL)'], [S('pkaCovDrop'), cov.drop, 'url(#hxbar)'], [S('pkaCovNow'), cov.impute, 'var(--text)']]
      .map(function (r, i) {
        var y = 8 + i * RH, w = Math.max(2, (r[1] || 0) / mx * PW);
        return rowLabel(padL - 10, y + 15, r[0], padL) + rect(padL, y, w, 20, r[2], ' stroke="var(--text)" stroke-width=".7"') +
          txt(padL + w + 8, y + 15, n0(r[1]), 'hs-vlab', 'start');
      }).join('');
    var figC = fig(S('pkaCovT'), Sf('pkaCovS', n0(-Bd.buildings_delta), n0(C.buildings), n0(cov.parking_drop_rung)), svg(W_, H, body, 'hs-axis'));
    var trade = '<p class="hs-prose">' + esc(Sf('pkaTrade', n0(-Bd.buildings_delta), (-Bd.buildings_delta / C.buildings * 100).toFixed(1),
      f2(ex.only_unpriced_gross_as_now), f2(ex.rest_gross_as_now), n0(ex.only_unpriced_built_median), n0(ex.rest_built_median),
      (ex.only_unpriced_tower_pct == null ? '--' : ex.only_unpriced_tower_pct.toFixed(1)), (ex.rest_tower_pct == null ? '--' : ex.rest_tower_pct.toFixed(1)),
      n0(C.buildings), A.gross.toFixed(2), C.gross.toFixed(2), (-A.gross_delta_pp >= 0 ? '+' : '') + (-A.gross_delta_pp).toFixed(3), A.net.toFixed(2), C.net.toFixed(2))) + '</p>';

    return '<div style="margin-top:var(--sp6)"><h3>' + esc(S('pkaH')) + '</h3>' +
      '<p class="hs-prose">' + esc(Sf('pkaP', s100, n0(P.n), f2(P.median), f2(P.lo), f2(P.hi), f2(P.q1), f2(P.q3))) + '</p>' +
      '<div class="hs-callout"><p>' + esc(Sf(vkey, f2(V.lo), f2(V.hi), s100, f2(V.hold_band[0]), f2(V.hold_band[1]))) + '</p></div>' +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('pkaRule', n0(V.min_n), V.equal_margin.toFixed(2), f2(V.hold_band[0]), f2(V.hold_band[1]), V.equal_margin.toFixed(2))) + '</p>' +
      table + corr + who + socP +
      '<h3>' + esc(S('pkaBoundsH')) + '</h3>' + cards + expo + figC + trade +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('pkaNote', D.headline.yield.toFixed(2), D.headline.net.toFixed(2), A.gross.toFixed(2), A.net.toFixed(2))) + '</p></div>';
  }

  function secNet() {
    var A = D.assumptions || [], a = asm();
    var sliders = A.map(function (s) {
      return '<div><div class="hs-asm-h"><span class="hs-asm-t">' +
        esc(LANG === 'zh' ? s.zh : s.en) + '</span>' +
        '<span class="hs-asm-v" data-asmv="' + s.key + '">' + a[s.key] + '</span></div>' +
        '<div class="hs-asm-u">' + esc(s.unit) + '</div>' +
        '<input type="range" data-asm="' + s.key + '" aria-label="' + esc(LANG === 'zh' ? s.zh : s.en) + '" min="' + s.min + '" max="' + s.max +
          '" step="' + s.step + '" value="' + a[s.key] + '">' +
        '<div class="hs-asm-s"><strong>' + esc(S('srcLabel')) + '</strong> ' +
          esc(LANG === 'zh' ? s.src_zh : s.src_en) + '</div></div>';
    }).join('');
    return sec('netEy', 'netH', 1,
      '<p class="hs-prose">' + esc(S('netP')) + '</p>' +
      '<div class="hs-card" style="margin-bottom:var(--sp5)"><div class="hs-wf" id="hs-wf"></div></div>' +
      '<div class="hs-card"><div class="hs-assume">' + sliders + '</div>' +
        '<div style="margin-top:var(--sp5)"><button class="hs-btn" id="hs-asmreset">' +
        esc(S('reset')) + '</button></div></div>' +
      vacancyPrior() + mgmtExposure() + mgmtFlag());
  }

  // The vacancy term is the only cost assumption with no source at all. Its
  // LEVEL cannot be sourced -- Taiwan publishes no rental-vacancy rate -- so
  // this block sources its SHAPE instead, from 內政部's county x age-band
  // cross-table, and is explicit that the two are different constructs. The
  // headline stays flat; the shaped and literal-level cases are published
  // beside it, and the toggle recomputes the whole page so a reader can see
  // what the shape does rather than take this block's word for it.
  function vacancyPrior() {
    var v = D.vacancy_prior;
    if (!v || !v.cases || v.cases.length < 3 || !v.profile || !v.profile.length) return '';
    var C = {}; v.cases.forEach(function (c) { C[c.key] = c; });
    if (!C.flat || C.flat.net == null || v.national_pct == null) return '';
    function f2(x) { return x == null ? '--' : x.toFixed(2); }
    function card(c, label, muted) {
      return '<div class="hs-vs-item' + (muted ? ' muted' : '') + '">' +
        '<div class="hs-vs-v">' + f2(c.net) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) +
        (muted ? '<br><span class="hs-sub2">' + (c.delta_pp >= 0 ? '+' : '') +
          // 3dp renders a real -0.0002 as "-0.000", which reads as a rounding
          // artefact rather than the near-zero the normalisation guarantees
          c.delta_pp.toFixed(Math.abs(c.delta_pp) < 0.001 ? 4 : 3) + 'pp</span>' : '') +
        '</div></div>';
    }
    // the age profile: one bar per band, labelled at BOTH ends -> natural width
    var P = v.profile;
    // padR holds the right-hand "matched X% / stock Y%" label, which is far
    // wider in English than in Chinese; at 150 the longest bar's own value
    // label collided with it.
    var W = 600, padL = 78, padR = 200, RH = 30, padT = 20;
    var H = padT + P.length * RH + 14;
    var mx = Math.max.apply(null, P.map(function (x) { return x.rate_pct; }));
    var X = function (r) { return padL + r / (mx * 1.05) * (W - padL - padR); };
    var body = line(X(v.national_pct), padT - 6, X(v.national_pct), H - 8, 'var(--subtle)', 1) +
      txt(X(v.national_pct), padT - 10, Sf('vacNatTick', f2(v.national_pct)), 'hs-glab',
          'middle', ' style="fill:var(--subtle);font-size:9.5px"');
    P.forEach(function (bd, i) {
      var y = padT + i * RH;
      body += txt(padL - 8, y + 15, Sf('vacBandLab', bd.band), 'hs-glab', 'end') +
        rect(padL, y + 4, Math.max(2, X(bd.rate_pct) - padL), 15, 'url(#hxbar)',
             ' stroke="var(--text)" stroke-width="0.9"') +
        txt(X(bd.rate_pct) + 5, y + 16, f2(bd.rate_pct) + '%', 'hs-vlab', 'start',
            ' style="font-size:10px"') +
        txt(W - 6, y + 16,
            Sf('vacMatch', f2(bd.matched_share_pct)) +
            (bd.stock_share_pct == null ? '' : ' · ' + Sf('vacStock', f2(bd.stock_share_pct))),
            'hs-glab', 'end', ' style="fill:var(--subtle);font-size:9.5px"');
    });
    var newest = P[0] || {};
    var tg = {}; (v.type_gap || []).forEach(function (g) { tg[g.case] = g; });
    var cl = v.county_leg || {};
    var st = v.stability || {};
    return '<div style="margin-top:var(--sp6)"><h3>' + esc(S('vacH')) + '</h3>' +
      '<p class="hs-prose">' + esc(Sf('vacP', f2(v.site_default_pct))) + '</p>' +
      '<div class="hs-callout"><p>' + esc(S('vacNot')) + '</p></div>' +
      '<p class="hs-prose">' + esc(Sf('vacFind', v.period, n0(D.headline.buildings),
        f2(v.prior_pct), f2(v.prior_ci[0]), f2(v.prior_ci[1]), f2(v.national_pct),
        f2(v.gap_pp), f2(newest.rate_pct), f2(newest.matched_share_pct),
        f2(newest.stock_share_pct))) + '</p>' +
      fig(S('vacProfH'), Sf('vacProfN', v.period), svg(W, H, body, 'hs-axis')) +
      (cl.prior_pct != null ? '<p class="hs-prose">' + esc(Sf('vacCounty', cl.period,
        n0(cl.counties), f2(cl.prior_pct), f2(cl.national_pct),
        f2(Math.abs(cl.gap_pp)))) + '</p>' : '') +
      (st.prior_pct != null ? '<p class="hs-fig-n hs-prose">' + esc(Sf('vacStab', st.period,
        f2(st.prior_pct), f2(st.national_pct), f2(st.gap_pp), cl.period || '--')) + '</p>' : '') +
      '<h3 style="margin-top:var(--sp5)">' + esc(S('vacCases')) + '</h3>' +
      '<div class="hs-vs" style="max-width:640px">' +
        card(C.flat, S('vacFlat'), false) + card(C.shape, S('vacShape'), true) +
        card(C.level, S('vacLevel'), true) +
      '</div>' +
      '<p class="hs-prose">' + esc(Sf('vacShapeP', f2(v.site_default_pct),
        f2(C.shape.vacancy_min_pct), f2(C.shape.vacancy_max_pct),
        Math.abs(C.shape.delta_pp).toFixed(4), f2(C.flat.net), f2(C.level.net))) + '</p>' +
      (tg.flat && tg.flat.gap_pp != null ? '<p class="hs-prose">' + esc(Sf('vacGap',
        tg.flat.gap_pp.toFixed(2), tg.shape.gap_pp.toFixed(2),
        tg.level.gap_pp.toFixed(2))) + '</p>' : '') +
      '<label class="hs-check"><input type="checkbox" id="hs-vshape"' +
        (state.vshape ? ' checked' : '') + '> ' + esc(S('vacToggle')) + '</label>' +
      '<p class="hs-fig-n hs-prose">' + esc(S('vacToggleN')) + '</p>' +
      '<p class="hs-fig-n hs-prose">' + esc(S('vacGone')) + '</p>' +
      '<p class="hs-fig-n hs-prose">' + esc(LANG === 'zh' ? v.source_zh : v.source_en) +
        ' · ' + esc(LANG === 'zh' ? v.period_zh : v.period_en) + '</p>' +
      '</div>';
  }

  // The management fee has a published source for 臺北 and 新北 and for nowhere
  // else, and the site now covers 22 counties -- so 20 of them are charged New
  // Taipei's rate because there is no per-county statistic to charge instead.
  // That cannot be corrected, so it is measured: what the net yield does if the
  // rate is halved or removed. Same treatment as the vacancy assumption.
  function mgmtExposure() {
    var m = D.mgmt_exposure;
    if (!m || !m.cases || m.cases.length < 3) return '';
    var base = m.cases[0];
    var half = m.cases.filter(function (c) { return c.case === 'half'; })[0];
    var zero = m.cases.filter(function (c) { return c.case === 'zero'; })[0];
    if (!half || !zero || base.net == null) return '';
    function card(c, label, muted) {
      return '<div class="hs-vs-item' + (muted ? ' muted' : '') + '">' +
        '<div class="hs-vs-v">' + c.net.toFixed(2) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) +
        (muted ? '<br><span class="hs-sub2">' + (c.delta_pp >= 0 ? '+' : '') +
          c.delta_pp.toFixed(3) + 'pp</span>' : '') + '</div></div>';
    }
    return '<div style="margin-top:var(--sp6)"><h3>' + esc(S('mgxH')) + '</h3>' +
      '<p class="hs-prose">' + esc(Sf('mgxP', n0(m.buildings_charged),
          m.counties_outside, m.share_charged_pct.toFixed(1))) + '</p>' +
      '<div class="hs-vs" style="max-width:640px">' +
        card(base, S('mgxBase'), false) + card(half, S('mgxHalf'), true) +
        card(zero, S('mgxZero'), true) +
      '</div>' +
      '<p class="hs-fig-n hs-prose">' + esc(S('mgxNote')) + '</p></div>';
  }


  // What the lease itself says about the fee. The site charges a fee on one
  // registry field (有無管理員); this reports what a second field (備註) says
  // about who pays it. Two bounds, headline untouched: unstated is not evidence.
  function mgmtFlag() {
    var mf = D.mgmt_flag;
    if (!mf || !mf.bounds || mf.bounds.length < 2 || !mf.lets) return '';
    var A = mf.bounds[0], Bb = mf.bounds[1], L_ = mf.lets, Bd = mf.buildings, wb = mf.within_building || {};
    function card(c, label, muted) {
      return '<div class="hs-vs-item' + (muted ? ' muted' : '') + '">' +
        '<div class="hs-vs-v">' + c.net.toFixed(2) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) +
        (muted ? '<br><span class="hs-sub2">' + (c.delta_pp >= 0 ? '+' : '') + c.delta_pp.toFixed(3) + 'pp</span>' : '') +
        (c.lo != null ? '<br><span class="hs-sub2">' + esc(Sf('ci95', c.lo.toFixed(2), c.hi.toFixed(2))) + '</span>' : '') +
        '</div></div>';
    }
    // by lease quarter: a column chart, the partial first and censored last columns marked
    var rows = mf.by_quarter || [], figQ = '';
    if (rows.length >= 3) {
      // natural width: twelve labelled columns scroll on a phone, not shrink
      var W = 620, H = 200, padL = 40, padB = 40, padT = 26;
      var PW = W - padL - 14, cw = PW / rows.length, bw = Math.max(8, cw * 0.62);
      var yOf = function (p) { return H - padB - p / 60 * (H - padT - padB); };
      var body = [20, 40, 60].map(function (t) {
        return line(padL, yOf(t) + 0.5, W - 14, yOf(t) + 0.5, 'var(--grid)', 1) +
          txt(padL - 6, yOf(t) + 4, t + '%', 'hs-axis', 'end', ' style="fill:var(--muted);font-size:10px"');
      }).join('');
      rows.forEach(function (r, i) {
        var x = padL + i * cw + (cw - bw) / 2, y = yOf(Math.min(60, r.incl_pct));
        var edge = r.partial || r.censored;
        body += rect(x, y, bw, H - padB - y, edge ? 'url(#hxbarL)' : 'url(#hxbar)',
                     ' stroke="var(--text)" stroke-width=".7"') +
          txt(x + bw / 2, y - 3, r.incl_pct.toFixed(1), 'hs-vlab', 'middle', ' style="font-size:10.5px"') +
          txt(x + bw / 2, H - padB + 12, r.q, 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:10px"') +
          txt(x + bw / 2, H - padB + 24, n0(r.lets), 'hs-glab', 'middle', ' style="fill:var(--subtle);font-size:9.5px"') +
          (edge ? txt(x + bw / 2, padT - 8, S(r.partial ? 'mgfPartial' : 'mgfCensored'), 'hs-glab', 'middle',
                      ' style="fill:var(--muted);font-size:10px"') : '');
      });
      var full = rows.filter(function (r) { return !r.partial && !r.censored; });
      figQ = fig(S('mgfQT'), S('mgfQS'), svg(W, H, body, 'hs-axis')) +
        (full.length >= 2 ? '<p class="hs-prose">' + esc(Sf('mgfTrend',
            full[0].q, full[0].incl_pct.toFixed(1), full[full.length - 1].q, full[full.length - 1].incl_pct.toFixed(1))) + '</p>' : '');
    }
    // by county: 筆 and 棟 in separate columns
    var tbl = '';
    if (mf.by_county && mf.by_county.length) {
      var o = mf.by_county_other || {};
      var tr = function (name, r) {
        return '<tr><td>' + esc(name) + '</td><td class="num">' + n0(r.lets) + '</td>' +
          '<td class="num">' + (r.incl_pct == null ? n0(r.incl) : r.incl_pct.toFixed(1) + '%') + '</td>' +
          '<td class="num">' + (r.excl_pct == null ? n0(r.excl) : r.excl_pct.toFixed(1) + '%') + '</td>' +
          '<td class="num">' + n0(r.bldgs) + '</td>' +
          '<td class="num">' + n0(r.bldgs_flag_any) + (r.bldgs_flag_any_pct == null ? '' : ' (' + r.bldgs_flag_any_pct.toFixed(0) + '%)') + '</td></tr>';
      };
      tbl = '<div class="hs-scroll"><table aria-label="' + esc(S('mgfCountyT')) + '" style="font-size:13.5px">' +
        '<thead><tr><th></th><th class="num">' + esc(S('thLets')) + '</th><th class="num">' + esc(S('thIncl')) + '</th>' +
        '<th class="num">' + esc(S('thExcl')) + '</th><th class="num">' + esc(S('thBldgs')) + '</th>' +
        '<th class="num">' + esc(S('thBldgsFlag')) + '</th></tr></thead><tbody>' +
        mf.by_county.map(function (r) { return tr(countyName(r.county), r); }).join('') +
        tr(S('thOther'), o) + '</tbody></table></div>' +
        '<p class="hs-fig-n">' + esc(S('mgfCountyT')) + '</p>';
    }
    var assumed = wb.assumed_ntd_ping_mo || {};
    return '<div style="margin-top:var(--sp6)"><h3>' + esc(S('mgfH')) + '</h3>' +
      '<p class="hs-prose">' + esc(Sf('mgfP', L_.incl_pct.toFixed(1), L_.excl_pct.toFixed(1), L_.unstated_pct.toFixed(1),
          n0(L_.has_mgr), n0(Bd.has_mgr), n0(Bd.flag_any), Bd.flag_any_pct.toFixed(1))) + '</p>' +
      '<div class="hs-vs" style="max-width:640px">' + card(A, S('mgfA'), false) + card(Bb, S('mgfB'), true) + '</div>' +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('mgfRule', n0(Bd.flag_majority),
          (Bd.flag_majority_delta_pp == null ? '--' : Bd.flag_majority_delta_pp.toFixed(3)))) + '</p>' +
      figQ + tbl +
      (wb.n ? '<p class="hs-prose">' + esc(Sf('mgfWb', wb.median_pct.toFixed(1), n0(wb.n), wb.q1_pct.toFixed(1),
          wb.q3_pct.toFixed(1), wb.share_pos_pct.toFixed(0), n0(wb.gap_ntd_ping_mo), n0(wb.rent_ping_mo),
          n0(assumed.f), n0(assumed.a))) + '</p>' : '') +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('mgfNote', L_.unstated_pct.toFixed(1), D.headline.net.toFixed(2))) + '</p></div>';
  }

  function renderWaterfall() {
    var host = document.getElementById('hs-wf');
    if (!host) return;
    var a = asm(), B = filtered();
    // Median across buildings of each per-building component, expressed as a
    // share of price. NOTE they still do not SUM to the total: every row is the
    // median of its own cost across buildings, the last row is the median of
    // the per-building net, and a median is not additive. Measured, the rows
    // subtract to 1.76 where the net is 1.73. The caption says so rather than
    // the chart pretending otherwise.
    var comp = B.map(function (b) {
      if (!b.pa || !b.rm) return null;
      var annual = b.rm * 12;
      var mgmtRate = b.c === 'a' ? a.mgmt : a.mgmt * (105 / 140);
      var age = b.b == null ? 0 : Math.max(0, 115 - b.b);
      return {
        gross: annual / b.pa * 100,
        vac: annual * ((a.vacancy * (state.vshape && b.vs ? b.vs : 1)) / 100) / b.pa * 100,
        tax: a.tax,
        mgmt: (b.m ? mgmtRate * b.ar * 12 : 0) / b.pa * 100,
        rep: annual * (a.repairs / 100) * (1 + age / 50) / b.pa * 100
      };
    }).filter(Boolean);
    if (!comp.length) { host.innerHTML = ''; return; }
    var g = medianOf(comp.map(function (c) { return c.gross; }));
    // 'solid' = a yield that exists; 'hollow' = a deduction taken out of it.
    // In one ink these two cannot be told apart by colour, and they are the
    // whole point of the chart, so they are told apart by texture instead.
    var rows = [
      [S('wfGross'), g, 'solid'],
      [S('wfVac'), -medianOf(comp.map(function (c) { return c.vac; })), 'hollow'],
      [S('wfTax'), -medianOf(comp.map(function (c) { return c.tax; })), 'hollow'],
      [S('wfMgmt'), -medianOf(comp.map(function (c) { return c.mgmt; })), 'hollow'],
      [S('wfRep'), -medianOf(comp.map(function (c) { return c.rep; })), 'hollow']
    ];
    var net = medianOf(B.map(function (b) { return netYield(b, a); }));
    var html = rows.map(function (r) {
      var w = Math.abs(r[1]) / g * 100;
      return '<div class="hs-wf-row"><span class="hs-wf-l">' + esc(r[0]) + '</span>' +
        '<span class="hs-wf-bar"><i class="hs-wf-fill ' + r[2] + '" style="left:0;width:' +
          w.toFixed(1) + '%"></i></span>' +
        '<span class="hs-wf-v">' + (r[1] >= 0 ? '' : '-') + Math.abs(r[1]).toFixed(2) + '</span></div>';
    }).join('') +
      '<div class="hs-wf-row total"><span class="hs-wf-l">' + esc(S('wfNet')) + '</span>' +
      '<span class="hs-wf-bar"><i class="hs-wf-fill solid" style="left:0;width:' +
        Math.max(0, net / g * 100).toFixed(1) + '%"></i></span>' +
      '<span class="hs-wf-v">' + (net == null ? '--' : net.toFixed(2) + '%') + '</span></div>';
    if (D.mgmt_flag && D.mgmt_flag.bounds) {
      var netF = medianOf(B.map(function (b) { return netYield(b, a, 'flag'); }));
      html += '<div class="hs-wf-row muted"><span class="hs-wf-l">' + esc(S('wfMgmtFlag')) + '</span>' +
        '<span class="hs-wf-bar"><i class="hs-wf-fill hollow" style="left:0;width:' +
          Math.max(0, netF / g * 100).toFixed(1) + '%"></i></span>' +
        '<span class="hs-wf-v">' + (netF == null ? '--' : netF.toFixed(2) + '%') + '</span></div>';
    }
    if (D.parking_audit && D.parking_audit.treatments) {
      // b.ro = the building's median rent under the old treatment (no imputed
      // space rent taken out); a copy, never a mutation of the building record
      var netI = medianOf(B.map(function (b) {
        return netYield(b.ro == null ? b : Object.assign({}, b, { rm: b.ro }), a);
      }));
      html += '<div class="hs-wf-row muted"><span class="hs-wf-l">' + esc(S('wfParkOld')) + '</span>' +
        '<span class="hs-wf-bar"><i class="hs-wf-fill hollow" style="left:0;width:' +
          Math.max(0, netI / g * 100).toFixed(1) + '%"></i></span>' +
        '<span class="hs-wf-v">' + (netI == null ? '--' : netI.toFixed(2) + '%') + '</span></div>';
    }
    var _sub = g - medianOf(comp.map(function (c) { return c.vac; }))
              - medianOf(comp.map(function (c) { return c.tax; }))
              - medianOf(comp.map(function (c) { return c.mgmt; }))
              - medianOf(comp.map(function (c) { return c.rep; }));
    html += '<p class="hs-fig-n hs-prose" style="margin-top:var(--sp4)">' +
      esc(Sf('wfNote', Math.abs(_sub - net).toFixed(2), D.headline.yield.toFixed(2))) + '</p>';
    host.innerHTML = html;
    var nf = document.getElementById('hs-netfig');
    if (nf) nf.textContent = net == null ? '--' : net.toFixed(2) + '%';
  }


  function secPostStrat() {
    var ps = D.post_strat;
    if (!ps || !ps.by_both) return '';
    var W = chartW(620), H = 250, padL = 54, padB = 34, padT = 14;
    var ds = ps.deciles, bw = (W - padL - 16) / ds.length;
    var mx = Math.max.apply(null, ds.map(function (d) { return Math.max(d.universe, d.matched); }));
    var bars = ds.map(function (d, i) {
      var x = padL + i * bw;
      var hu = d.universe / mx * (H - padT - padB);
      var hm = d.matched / mx * (H - padT - padB);
      return rect(x + 1, H - padB - hu, bw / 2 - 2, hu, 'url(#hxbarL)',
                  ' stroke="var(--text)" stroke-width=".7"') +
        rect(x + bw / 2 + 1, H - padB - hm, bw / 2 - 2, hm, 'url(#hxbar)',
             ' stroke="var(--text)" stroke-width=".7"') +
        txt(x + bw / 2, H - 18, d.d, 'hs-axis', 'middle',
            ' style="fill:var(--muted);font-size:10.5px"') +
        (d.ratio >= 1.5 || d.ratio <= 0.5
          ? txt(x + bw / 2, H - padB - Math.max(hu, hm) - 6, d.ratio + 'x', 'hs-vlab', 'middle',
                ' style="font-size:10.5px"') : '');
    }).join('');
    var lg = '<div class="hs-legend">' +
      '<b><i class="hs-swatch hx-lo"></i>' + esc(S('psVis') === '' ? '' : (LANG === 'zh' ? '實際房屋結構' : 'All buildings that sold')) + '</b>' +
      '<b><i class="hs-swatch hx-hi"></i>' + esc(LANG === 'zh' ? '配對樣本' : 'Matched sample') + '</b></div>';
    var top = ds[ds.length - 1];
    return sec('psEy', 'psH', 1,
      '<p class="hs-prose">' + esc(Sf('psP', n0(D.headline.buildings),
          n0(D.headline.universe_buildings), top.matched)) + '</p>' +
      '<div class="hs-vs" style="max-width:640px;margin-bottom:var(--sp6)">' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' + ps.visible_gross.toFixed(2) +
          '%</div><div class="hs-vs-l">' + esc(S('psVis')) + '</div></div>' +
        '<div class="hs-vs-item"><div class="hs-vs-v" style="color:var(--accent)">' +
          ps.by_both.gross.toFixed(2) + '%</div><div class="hs-vs-l">' + esc(S('psAdj')) +
          ' (' + (ps.shift_pp >= 0 ? '+' : '') + ps.shift_pp.toFixed(2) + 'pp)</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' + ps.by_type.gross.toFixed(2) +
          '%</div><div class="hs-vs-l">' + esc(S('psByType')) + '</div></div>' +
      '</div>' +
      fig(S('psDecile'), null, svg(W, H, bars), lg) +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('psNote',
          (ps.by_type.gross - ps.visible_gross).toFixed(3),
          (ps.by_price.gross - ps.visible_gross).toFixed(3),
          (ps.by_both.gross - ps.visible_gross).toFixed(3))) + '</p>');
  }

  // Geocoding is all-or-nothing per county: a county whose government has
  // published an address-point file matches nearly everything, one that has not
  // matches nothing. The copy used to name which counties from memory and got it
  // wrong (it claimed Hsinchu was above 98%; Hsinchu is at 0%). Counted instead.
  var _geoSplit = null;
  function geoSplit() {
    if (_geoSplit) return _geoSplit;
    var tot = {}, got = {};
    (D.buildings || []).forEach(function (b) {
      tot[b.c] = (tot[b.c] || 0) + 1;
      if (b.mx != null && b.my != null) got[b.c] = (got[b.c] || 0) + 1;
    });
    var high = 0, none = 0, mid = [];
    Object.keys(tot).forEach(function (c) {
      var r = (got[c] || 0) / tot[c];
      if (r >= 0.98) high++;
      else if (!got[c]) none++;
      else mid.push({ c: c, pct: r * 100 });
    });
    // the counties that are neither: partial address files. Reported, so the
    // counts add up to the number of counties on the map.
    _geoSplit = { high: high, none: none,
                  midName: mid.length ? countyName(mid[0].c) : '',
                  midPct: mid.length ? mid[0].pct : null, midN: mid.length };
    return _geoSplit;
  }

  function ciNoteText(atCounty) {
    var B = D.bootstrap || {};
    // adjacent_overlaps/adjacent_pairs are computed over the 80 DISTRICTS. The
    // ranking opens at county level, where the answer is different (11 of 13,
    // and two pairs genuinely separate) -- so the district sentence was being
    // printed under a 14-county chart, naming two districts as its extremes.
    if (atCounty) {
      // "Adjacent" has to mean adjacent ON THE CHART, and the chart is drawn
      // straight from D.counties, which the build sorts by the county's
      // published MEDIAN. Sorting here by the CI midpoint instead put 基隆市
      // and 臺南市 in the wrong order, which moved 臺南市 up against 高雄市
      // and manufactured a separating pair the reader cannot see: it printed
      // 10 of 13 where the chart's own order gives 11 of 13. The strict `>`
      // matches underwrite.py's district rule, so both sentences on this page
      // mean the same thing by "overlap".
      var rows = (D.counties || []).map(function (c) {
        var v = (B.county || {})[c.county];
        return v && v.lo != null ? { k: c.county, lo: v.lo, hi: v.hi } : null;
      }).filter(Boolean);
      if (rows.length < 3) return '';
      var ov2 = 0, sep = [];
      for (var i = 0; i < rows.length - 1; i++) {
        if (rows[i].hi > rows[i + 1].lo) ov2++;
        else sep.push(countyName(rows[i].k) + '／' + countyName(rows[i + 1].k));
      }
      return Sf('ciNoteCty', ov2, rows.length - 1,
                sep.length ? sep.join('、') : '—');
    }
    var ov = B.adjacent_overlaps, np = B.adjacent_pairs;
    if (ov == null || np == null) return '';
    // two slots, like the sibling keys: composing "X of Y" here put an
    // English connective inside the Chinese sentence.
    if (ov < np) return Sf('ciNote', ov, np);
    // Every neighbouring pair overlaps. Find the extremes that do not.
    var rows = [];
    Object.keys(B.district || {}).forEach(function (k) {
      var v = B.district[k];
      if (v && v.lo != null) rows.push({ k: k, lo: v.lo, hi: v.hi, m: (v.lo + v.hi) / 2 });
    });
    if (rows.length < 2) return Sf('ciNote', ov, np);
    rows.sort(function (a, b) { return a.m - b.m; });
    var lo = rows[0], hi = rows[rows.length - 1];
    function nm(key) {
      var parts = String(key).split('|');
      var d = (D.districts || []).filter(function (x) { return x.district === parts[1]; })[0];
      return (d ? d.city : '') + parts[1];
    }
    return Sf('ciNoteAll', np, nm(lo.k), lo.lo.toFixed(2) + '–' + lo.hi.toFixed(2) + '%',
              nm(hi.k), hi.lo.toFixed(2) + '–' + hi.hi.toFixed(2) + '%');
  }

  // The county's low-electricity-use share from the MOI block, for a note
  // that used to have "10.9%" typed into it.
  function countyLowUsePct(city) {
    // moi.low_use carries 全國 plus the six special municipalities and nothing
    // else, so every other county used to render a literal '?' -- and the one
    // place this is called names 花蓮縣. v2.4's county leg ships all 22, keyed
    // by county code, so fall through to it before giving up.
    var lu = D.moi && D.moi.low_use;
    var r = lu && lu.rows && lu.rows.filter(function (x) { return x.city === city; })[0];
    if (r) return r.rate_pct.toFixed(1);
    var cl = D.vacancy_prior && D.vacancy_prior.county_leg;
    if (cl && cl.rows) {
      var code = Object.keys(COUNTY).filter(function (k) { return COUNTY[k][0] === city; })[0];
      var q = code && cl.rows.filter(function (x) { return x.county === code; })[0];
      if (q) return q.rate_pct.toFixed(1);
    }
    return '?';
  }

  function secDispersion() {
    var dp = D.dispersion;
    if (!dp || !dp.ratio) return '';
    var W = chartW(560);
    // Below 480 the left gutter cannot hold either series name -- at 375px it is
    // 112 units for strings 175-180 wide, and the SVG clips -- so the label goes
    // ABOVE its bar instead, the way secPartialId's ladder does.
    var narrow = W < 480;
    var padL = narrow ? 4 : Math.min(250, Math.round(W * 0.42));
    var RH = narrow ? 56 : 44, H = (narrow ? 26 : 18) + 2 * RH + 8;
    var mx = Math.max(dp.within_iqr, dp.between_iqr);
    var rows = [[S('dispWithin'), dp.within_iqr, 'var(--accent)'],
                [S('dispBetween'), dp.between_iqr, 'var(--dim)']]
      .map(function (r, i) {
        var y = (narrow ? 26 : 18) + i * RH, w = r[1] / mx * (W - padL - 90);
        return (narrow
                 ? txt(padL, y - 6, r[0], 'hs-glab', 'start')
                 : txt(padL - 12, y + 18, r[0], 'hs-glab', 'end')) +
          rect(padL, y + 4, w, 24, r[2], '') +
          txt(padL + w + 10, y + 21, r[1].toFixed(3) + ' pp', 'hs-vlab', 'start');
      }).join('');
    // This section published "one building spreads Nx wider than the whole city"
    // for months. That was measured on Taipei + New Taipei, where it was true.
    // It does NOT survive going national: 22 counties spread the between-district
    // term far wider than 12 Taipei districts did, and the ratio inverts. The
    // copy now follows the ratio in both directions instead of asserting one.
    var wider = dp.ratio > 1;
    var nDist = (D.districts || []).length || 0;
    return sec('dispEy', null, 1,
      '<h2>' + esc(wider ? Sf('dispH', dp.ratio.toFixed(2))
                         : Sf('dispHN', (1 / dp.ratio).toFixed(2))) + '</h2>' +
      '<p class="hs-prose lede">' + esc(wider
        ? Sf('dispP', n0(dp.buildings), dp.within_iqr.toFixed(2), nDist,
             dp.between_iqr.toFixed(2))
        : Sf('dispPN', n0(dp.buildings), dp.within_iqr.toFixed(2), nDist,
             dp.between_iqr.toFixed(2), dp.within_iqr.toFixed(2))) + '</p>' +
      (wider || MODE !== 'advanced' ? '' : '<p class="hs-plain">' + esc(S('dispFix')) + '</p>') +
      '<div class="hs-card hs-scroll">' + svg(W, H, rows, '', S('dispEy')) + '</div>');
  }

  // The comparison a reader actually arrives with. The page computes a net yield
  // and then leaves it floating against nothing; the cost of borrowing is the
  // number every buyer already has in their head, and it is published monthly by
  // the central bank. Quoting it is analysis. Drawing a conclusion from it would
  // not be, so the copy stops at "here are two numbers".
  function secMortgage() {
    var m = D.mortgage, h = D.headline;
    if (!m || h.net == null) return '';
    var diff = (h.net - m.rate);
    var word = Sf(diff < 0 ? 'mortGap' : 'mortSame', Math.abs(diff).toFixed(2));
    return sec('mortEy', 'mortH', 0,
      '<div class="hs-vs hs-mort">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + h.net.toFixed(2) + '%</div>' +
          '<div class="hs-vs-l">' + esc(S('heroNet')) + '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' + m.rate.toFixed(3) + '%</div>' +
          '<div class="hs-vs-l">' + esc(LANG === 'zh' ? m.src_zh : m.src_en) + '</div></div>' +
      '</div>' +
      '<p class="hs-mortgap">' + esc(word) + '</p>' +
      '<p class="hs-prose">' + esc(Sf('mortP', n0(h.buildings), h.net.toFixed(2),
        LANG === 'zh' ? m.src_zh : m.src_en, m.rate.toFixed(3),
        LANG === 'zh' ? m.period_zh : m.period_en)) + '</p>' +
      // both official rates here, not one here and one five screens down
      (D.moi && D.moi.mortgage ? '<p class="hs-fig-n hs-prose">' + esc(Sf('mortTwo',
          D.moi.mortgage.rate.toFixed(2), D.moi.mortgage.period,
          (D.moi.mortgage.rate - h.net).toFixed(2))) + '</p>' : '') +
      benchmarkStrip(h));
  }

  // "Compared to what." Three reference rates in one strip beside the net
  // yield -- ours solid, theirs muted, the grammar the mortgage tile already
  // uses. Every argument passed to bmP is a rate, a count or a period: no
  // expression here subtracts a benchmark from the yield, by design.
  function benchmarkStrip(h) {
    var dep = bmOf('deposit_1y'), red = bmOf('rediscount'), mort = bmOf('mortgage');
    if (!dep || !red || !mort) return '';
    function cell(b, label) {
      return '<div class="hs-vs-item muted"><div class="hs-vs-v">' + bmFmt(b) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) + '<br>' + esc(bmPeriod(b)) + '</div></div>';
    }
    var sameTxt = dep.same_at_all ? S('bmSame')
      : Sf('bmSpread', (Math.max.apply(null, Object.keys(dep.banks).map(function (k) { return dep.banks[k]; })) -
                        Math.min.apply(null, Object.keys(dep.banks).map(function (k) { return dep.banks[k]; }))).toFixed(3));
    return '<div class="hs-vs hs-bm">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + h.net.toFixed(2) + '%</div>' +
          '<div class="hs-vs-l">' + esc(S('heroNet')) + '</div></div>' +
        cell(dep, S('bmDep')) + cell(red, S('bmRed')) + cell(mort, S('bmMort')) +
      '</div>' +
      '<p class="hs-prose">' + esc(Sf('bmP', n0(h.buildings), h.net.toFixed(2),
        bmFmt(dep), bmPeriod(dep), sameTxt, bmFmt(red), bmPeriod(red),
        bmFmt(mort), bmPeriod(mort))) + '</p>' +
      [dep, red, mort].map(function (b) {
        var host = b.url.replace(/^https?:\/\//, '').split('/')[0];
        return '<p class="hs-fig-n">' + esc(LANG === 'zh' ? b.note_zh : b.note_en) +
          ' &middot; <a href="' + esc(b.url) + '" rel="noopener">' + esc(host) + '</a></p>';
      }).join('');
  }

  // Two attributes the registry has always carried and this project ignored,
  // measured with the same same-building design as the headline.
  function secIncome() {
    var I = D.income;
    if (!I || !I.counties || !I.counties.length) return '';
    var cs = I.counties, hi = cs[0], lo = cs[cs.length - 1];
    var max = hi.years;
    var shown = MODE === 'advanced' || cs.length <= 7 ? cs
      : cs.slice(0, 3).concat([null]).concat(cs.slice(-3));
    var rows = shown.map(function (r) {
      if (!r) return '<tr><td colspan="3" style="text-align:center;color:var(--subtle)">…' +
        esc(Sf('incElided', cs.length - 6)) + '</td></tr>';
      return '<tr><th scope="row">' + esc(r.city) + '</th>' +
        '<td class="hs-incbar"><i style="width:' + (r.years / max * 100).toFixed(1) + '%"></i></td>' +
        '<td class="hs-num">' + r.years.toFixed(1) + '</td></tr>';
    }).join('');
    var A2 = D.age || {};
    var _areaGap = (A2.matched_area && A2.unmatched_area)
      ? (A2.matched_area / A2.unmatched_area - 1) * 100 : null;
    // matched against the UNIVERSE, which is what this sentence compares; the
    // age block's gaps are matched against the UNMATCHED and answer a different
    // question, so multiplying them does not reproduce this figure.
    var _vsUniv = (I.matched_price && I.universe_price)
      ? (I.matched_price / I.universe_price - 1) * 100 : null;
    return sec('incEy', 'incH', 0,
      '<p class="hs-prose">' + esc(Sf('incP',
        LANG === 'zh' ? I.source_zh : I.source_en,
        // every one of these used to be typed into the string; when `age` moved
        // to the universe frame the typed ones went stale AND the sentence's
        // direction flipped -- the sliver's total price is now slightly HIGHER,
        // not 4.7% lower, which is what income_block's docstring always said.
        (I.universe_price == null ? '--' : n0(I.universe_price)),
        (I.matched_price == null ? '--' : n0(I.matched_price)),
        (_vsUniv == null ? '--' : Math.abs(_vsUniv).toFixed(1)),
        (I.matched_years == null ? '--' : I.matched_years.toFixed(1)),
        (I.national_years == null ? '--' : I.national_years.toFixed(1)),
        (A2 && A2.ppp_diff_pct != null ? A2.ppp_diff_pct.toFixed(1) : '--'))) + '</p>' +
      '<div class="hs-vs hs-mort">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + hi.years.toFixed(1) + '</div>' +
          '<div class="hs-vs-l">' + esc(hi.city + ' ' + S('incUnit')) + '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' + lo.years.toFixed(1) + '</div>' +
          '<div class="hs-vs-l">' + esc(lo.city + ' ' + S('incUnit')) + '</div></div>' +
      '</div>' +
      '<div class="hs-scroll"><table class="hs-inctab" aria-label="' + esc(S('incH')) + '"><tbody>' + rows + '</tbody></table></div>' +
      '<p class="hs-fig-n hs-prose">' + esc(Sf('incNote', I.year)) + '</p>');
  }

  function secWithin() {
    var w = D.within_building;
    if (!w || (!w.furnished && !w.floor)) return '';
    var f = w.furnished, fl = w.floor;
    var cards = '';
    if (f) {
      cards += '<div class="hs-vs-item"><div class="hs-vs-v">+' + f.pct.toFixed(1) + '%</div>' +
        '<div class="hs-vs-l">' + esc(S('wbFurn')) + '<br><span class="hs-sub2">' +
        esc(Sf('wbFurnN', n0(f.buildings))) + '</span></div></div>';
    }
    if (fl) {
      cards += '<div class="hs-vs-item muted"><div class="hs-vs-v">+' +
        fl.pct_per_floor.toFixed(2) + '%</div>' +
        '<div class="hs-vs-l">' + esc(S('wbFloorR')) + '<br><span class="hs-sub2">' +
        esc(Sf('wbFloorN', n0(fl.buildings))) + '</span></div></div>';
    }
    // The sale-side slope is the other half of the same question. On its own,
    // "rent rises 0.12% a floor" says nothing about whether climbing is worth
    // it; against the price slope it says which side of the trade the height
    // is being paid for on.
    var fs = w.floor_sale;
    if (fs && fs.pct_per_floor != null) {
      cards += '<div class="hs-vs-item"><div class="hs-vs-v">+' +
        fs.pct_per_floor.toFixed(2) + '%</div>' +
        // this card used the RENT card's string, so 22,274 sale-side buildings
        // were described as "buildings letting on 2+ floors"
        '<div class="hs-vs-l">' + esc(S('wbFloorS')) + '<br><span class="hs-sub2">' +
        esc(Sf('wbFloorSN', n0(fs.buildings))) + '</span></div></div>';
    }
    var gap = w.floor_gap_pp;
    // The heading carried "Furniture adds 3%" as literal text; it is 4.2%.
    // Emitted here rather than through sec() so it can take the real number.
    return sec('wbEy', null, 0,
      '<h2>' + esc(Sf('wbH', (f && f.pct != null ? f.pct : 0).toFixed(1))) + '</h2>' +
      '<p class="hs-prose">' + esc(S('wbP')) + '</p>' +
      // The other half of the identification pair. Everything in this section is
      // measured INSIDE one building, so the usual confounders are held constant
      // by construction rather than by assumption.
      '<p class="hs-prose hs-fig-n">' + esc(S('identWithin')) + '</p>' +
      '<div class="hs-vs hs-mort">' + cards + '</div>' +
      (gap != null && fs && fl
        ? '<p class="hs-plain">' + esc(Sf('wbFloorGap',
            fs.pct_per_floor.toFixed(2), n0(fs.buildings),
            fl.pct_per_floor.toFixed(2), n0(fl.buildings),
            gap.toFixed(2))) + '</p>'
        : (fl ? '<p class="hs-prose hs-fig-n">' +
            esc(Sf('wbFloorNote', fl.pct_per_floor.toFixed(2),
                (fl.pct_per_floor * 20).toFixed(1))) + '</p>' : '')));
  }


  // A parking space as its own asset, with the same identification the reader
  // has just been taught: same building, sale against lease. The unit is a
  // SPACE -- never 坪 -- and the dwelling yield beside it is context, not a
  // subtraction. Sits before the official figures because 內政部 publishes no
  // parking series to set beside it.
  function secParking() {
    var pk = D.parking;
    if (!pk || !pk.rungs || pk.rungs.length < 2) return '';
    var byKey = {}; pk.rungs.forEach(function (r) { byKey[r.key] = r; });
    var mk = byKey.market, wd = byKey.wide, st = byKey.strict;
    if (!mk) return '';
    var showWide = !!(wd && pk.wide_licensed);
    var pa = D.parking_audit, paT = pa && pa.treatments ? {} : null;
    if (paT) pa.treatments.forEach(function (t) { paT[t.case] = t; });
    function ci(r) { return r.lo == null ? '' : '<br><span class="hs-sub2">' + esc(Sf('ci95', r.lo.toFixed(2), r.hi.toFixed(2))) + '</span>'; }
    function card(r, label, muted) {
      return '<div class="hs-vs-item' + (muted ? ' muted' : '') + '"><div class="hs-vs-v">' + r.yield.toFixed(2) + '%</div>' +
        '<div class="hs-vs-l">' + esc(label) + ci(r) +
        '<br><span class="hs-sub2">' + esc(Sf('pkPriceRent', n0(r.price), n0(r.rent))) + ' · ' + n0(r.buildings) + ' ' + esc(S('rungBldgs')) + '</span></div></div>';
    }
    var lo_ = paT && paT.impute ? Math.min(paT.impute.gross, paT.drop.gross, paT.area_only.gross) : null;
    var hi_ = paT && paT.impute ? Math.max(paT.impute.gross, paT.drop.gross, paT.area_only.gross) : null;
    var dwell = '<div class="hs-vs-item muted"><div class="hs-vs-v">' + pk.dwelling.yield.toFixed(2) + '%</div>' +
      '<div class="hs-vs-l">' + esc(Sf('pkDwelling', pk.dwelling.yield.toFixed(2), n0(pk.dwelling.buildings),
        lo_ == null ? '--' : lo_.toFixed(2), hi_ == null ? '--' : hi_.toFixed(2))) + '</div></div>';

    // type dumbbell: filled = market, hollow = wide; horizontal so chartW applies
    var types = {};
    (pk.by_type.market || []).forEach(function (r) { types[r.type] = types[r.type] || {}; types[r.type].m = r; });
    if (showWide) (pk.by_type.wide || []).forEach(function (r) { types[r.type] = types[r.type] || {}; types[r.type].w = r; });
    var rows = Object.keys(types).sort(function (a, b) {
      return ((types[b].m || {}).buildings || 0) - ((types[a].m || {}).buildings || 0) ||
             ((types[b].w || {}).buildings || 0) - ((types[a].w || {}).buildings || 0);
    });
    // natural width: labels on both sides leave chartW() a 49px plot on a
    // phone; the card pans instead, like the column charts
    var W = 560, padL = 96, padR = 150, RH = 26, padT = 10;
    var H = padT + rows.length * RH + 24, PW = W - padL - padR;
    var xOf = function (v) { return padL + Math.min(4, Math.max(0, v)) / 4 * PW; };
    var body = [1, 2, 3, 4].map(function (t) {
      return line(xOf(t), padT, xOf(t), H - 20, 'var(--grid)', 1) +
        txt(xOf(t), H - 6, t + '%', 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:10px"');
    }).join('');
    rows.forEach(function (t, i) {
      var y = padT + i * RH + RH / 2, m = types[t].m, w = types[t].w;
      body += txt(padL - 10, y + 4, t, 'hs-glab', 'end');
      if (m && w) body += line(xOf(m.yield), y, xOf(w.yield), y, 'var(--grid)', 2);
      if (w) body += '<circle cx="' + xOf(w.yield).toFixed(1) + '" cy="' + y + '" r="5" fill="none" stroke="var(--text)" stroke-width="1.2"/>';
      if (m) body += '<circle cx="' + xOf(m.yield).toFixed(1) + '" cy="' + y + '" r="5" fill="var(--text)"/>';
      var lab = (m ? m.yield.toFixed(2) + '%' : '--') + (showWide ? ' / ' + (w ? w.yield.toFixed(2) + '%' : '--') : '');
      var nn = (m ? n0(m.buildings) : '--') + (showWide ? ' / ' + (w ? n0(w.buildings) : '--') : '');
      var xr = Math.max(xOf(m ? m.yield : 0), xOf(w ? w.yield : 0)) + 10;
      body += txt(xr, y + 1, lab, 'hs-vlab', 'start', ' style="font-size:10.5px"') +
        txt(xr, y + 12, nn, 'hs-glab', 'start', ' style="fill:var(--subtle);font-size:9.5px"');
    });
    var tg = pk.type_gap || {}, tgm = tg.market || {}, tgw = tg.wide || {};
    function pp(v) { return v == null ? '--' : (v >= 0 ? '+' : '') + v.toFixed(2) + 'pp'; }
    var ciM = tgm.lo == null ? Sf('pkNoCiN', n0(tgm.n_b), n0(pk.predicate.min_county_buildings))
                             : Sf('ci95', tgm.lo.toFixed(2), tgm.hi.toFixed(2));
    var fig1 = fig(S('pkTypeT'), Sf('pkTypeS', n0(pk.predicate.min_type_buildings)), svg(W, H, body, 'hs-axis'),
      '<div class="hs-fig-n">' + esc(Sf('pkTypeNote', mk.same_type_pairs_pct.toFixed(1), (wd ? wd.same_type_pairs_pct : 0).toFixed(1))) + '</div>');
    var mech = '<p class="hs-plain">' + esc(Sf('pkMech', pp(tgm.gap_pp), ciM, pp(tgw.gap_pp),
      tgw.lo == null ? '--' : tgw.lo.toFixed(2), tgw.hi == null ? '--' : tgw.hi.toFixed(2),
      tgm.price_ratio == null ? '--' : tgm.price_ratio.toFixed(2), tgm.rent_ratio == null ? '--' : tgm.rent_ratio.toFixed(2))) + '</p>';

    // county table, market rung: 棟 and yield with CI; price and rent per space
    var cty = pk.by_county.market || [], oth = pk.by_county.market_other || {};
    var tbl = '<div class="hs-scroll"><table aria-label="' + esc(Sf('pkCountyT', n0(pk.predicate.min_county_buildings))) + '" style="font-size:13.5px">' +
      '<thead><tr><th></th><th class="num">' + esc(S('pkThBldgs')) + '</th><th class="num">' + esc(S('pkThYield')) + '</th>' +
      '<th class="num">' + esc(S('pkThPrice')) + '</th><th class="num">' + esc(S('pkThRent')) + '</th></tr></thead><tbody>' +
      cty.map(function (r) {
        return '<tr><td>' + esc(countyName(r.county)) + '</td><td class="num">' + n0(r.buildings) + '</td>' +
          '<td class="num">' + r.yield.toFixed(2) + '%' + (r.lo == null ? '' : '<br><span class="hs-sub2">' + esc(Sf('ci95', r.lo.toFixed(2), r.hi.toFixed(2))) + '</span>') + '</td>' +
          '<td class="num">' + n0(r.price) + '</td><td class="num">' + n0(r.rent) + '</td></tr>';
      }).join('') +
      '<tr><td>' + esc(S('thOther')) + '</td><td class="num">' + n0(oth.buildings) + '</td><td class="num">--</td><td class="num">--</td><td class="num">--</td></tr>' +
      '</tbody></table></div><p class="hs-fig-n">' + esc(Sf('pkCountyT', n0(pk.predicate.min_county_buildings))) + '</p>';

    // advanced: the strict rung, the validations, the sensitivity, the records
    var adv = '';
    if (MODE === 'advanced') {
      var V = {}; (pk.validations || []).forEach(function (v) { V[v.key] = v; });
      var vrow = function (v, label) {
        return '<tr><td>' + esc(label) + (v.thin ? ' ' + esc(S('pkThin')) : '') + '</td><td class="num">' + n0(v.n) + '</td>' +
          '<td class="num">' + (v.median == null ? '--' : v.median.toFixed(3)) + '</td>' +
          '<td class="num">' + (v.q1 == null ? '--' : v.q1.toFixed(2) + '–' + v.q3.toFixed(2)) + '</td></tr>';
      };
      var sens = {}; (pk.sensitivity || []).forEach(function (x) { sens[x.key] = x; });
      var sl = sens.market_lease_standalone_only, ss = sens.market_sale_standalone_only;
      var inside = sl && ss && mk.lo != null && sl.yield >= mk.lo && sl.yield <= mk.hi && ss.yield >= mk.lo && ss.yield <= mk.hi;
      var v2 = V.social_vs_market_rent || {}, wr = pk.predicate.wide_rule || {};
      var rec = pk.records || {}, rs = rec.sale || {}, rr = rec.lease || {};
      var wfrow = function (label, n, sub) {
        return '<div class="hs-wf-row' + (sub ? ' muted' : '') + '"><span class="hs-wf-l">' + esc(label) + '</span><span class="hs-wf-bar"></span><span class="hs-wf-v">' + n0(n) + '</span></div>';
      };
      var unb = (pk.window_test || []).filter(function (w) { return w.window == null; })[0];
      adv = (st ? '<div class="hs-vs" style="max-width:640px;margin-top:var(--sp5)">' + card(st, S('pkRungStrict'), true) + '</div>' : '') +
        '<h3>' + esc(S('pkValidH')) + '</h3><p class="hs-prose">' + esc(S('pkValidP')) + '</p>' +
        '<div class="hs-scroll"><table aria-label="' + esc(S('pkValidH')) + '" style="font-size:13.5px"><thead><tr><th></th><th class="num">' + esc(S('pkThN')) + '</th><th class="num">' + esc(S('thRatio')) + '</th><th class="num">' + esc(S('thIqr')) + '</th></tr></thead><tbody>' +
        (V.bundled_sale_vs_standalone ? vrow(V.bundled_sale_vs_standalone, S('pkV1')) : '') +
        (V.social_vs_market_rent ? vrow(V.social_vs_market_rent, S('pkV2')) : '') +
        (V.bundled_lease_vs_standalone ? vrow(V.bundled_lease_vs_standalone, S('pkV3')) : '') +
        '</tbody></table></div>' +
        (V.bundled_lease_vs_standalone && sl && ss ? '<p class="hs-prose">' + esc(Sf('pkV3Thin', n0(V.bundled_lease_vs_standalone.n),
          sl.yield.toFixed(2), n0(sl.buildings), ss.yield.toFixed(2), n0(ss.buildings), S(inside ? 'pkInside' : 'pkOutside'))) + '</p>' : '') +
        '<p class="hs-fig-n hs-prose">' + esc(Sf('pkWideRule', (wr.max_abs_dev == null ? '--' : wr.max_abs_dev.toFixed(2)), n0(wr.min_n),
          v2.median == null ? '--' : v2.median.toFixed(3), n0(v2.n), S(pk.wide_licensed ? 'pkLicensed' : 'pkNotLicensed'))) + '</p>' +
        (wd ? '<p class="hs-fig-n hs-prose">' + esc(Sf('pkSocialNote', wd.social_pairs_pct.toFixed(1),
          (wd.top_county ? wd.top_county.buildings_pct : 0).toFixed(1), wd.top_county ? countyName(wd.top_county.county) : '--')) + '</p>' : '') +
        '<p class="hs-fig-n hs-prose">' + esc(Sf('pkBand', pk.predicate.yield_band[0], pk.predicate.yield_band[1], n0(mk.band_dropped), n0(wd ? wd.band_dropped : 0))) + '</p>' +
        (unb ? '<p class="hs-fig-n hs-prose">' + esc(Sf('pkTimeNote', pk.predicate.match_window_q, n0(mk.buildings), n0(unb.market.buildings), unb.market.yield == null ? '--' : unb.market.yield.toFixed(2))) + '</p>' : '') +
        '<h3>' + esc(S('pkWfT')) + '</h3><div class="hs-card"><div class="hs-wf">' +
        wfrow(S('pkWfSaleStand'), rs.single_standalone) + wfrow(S('pkWfSaleBund'), rs.single_bundled_itemised) +
        wfrow(S('pkWfLeaseStand'), rr.single_standalone) + wfrow(S('pkWfLeaseBund'), rr.single_bundled_priced) +
        wfrow(S('pkWfSocial'), rr.social, true) + '</div></div>';
    }

    return sec('pkEy', null, 0,
      '<h2>' + esc(Sf('pkH', n0(mk.price), n0(mk.rent), mk.yield.toFixed(2))) + '</h2>' +
      '<p class="hs-prose lede">' + esc(S('pkP')) + '</p>' +
      '<div class="hs-vs" style="max-width:' + (showWide ? '960' : '640') + 'px">' +
        card(mk, S('pkRungMarket'), false) + (showWide ? card(wd, S('pkRungWide'), true) : '') + dwell + '</div>' +
      fig1 + mech + tbl + adv);
  }

  // Is the walk-up advantage a building-type effect, or a price effect wearing
  // one? 公寓 sit in expensive central districts but are cheap per ping INSIDE
  // them, and price is the yield's denominator -- so the raw gap moves in
  // opposite directions depending on what you hold constant. Both controls are
  // computed here rather than asserted, because the raw figure alone reads as a
  // clean result and it is not one.
  function walkupControls() {
    var ALL = (D.buildings || []).filter(function (b) {
      return b.y != null && b.p != null;
    });
    var B = ALL.filter(function (b) { return b.t === '公寓' || b.t === '住宅大樓'; });
    if (B.length < 200) return null;
    // Cut the deciles over the WHOLE matched frame and only then restrict to
    // the two types, the way underwrite.py does (pd.qcut on `bb`, then
    // `pair_bb`). Cutting them over the 7,700-building subset instead moved
    // 25.8% of buildings into a different decile, so the page and the payload
    // were publishing two different answers for the same named control.
    var ps = ALL.map(function (b) { return b.p; }).sort(function (x, y) { return x - y; });
    var cuts = [];
    for (var i = 1; i < 10; i++) cuts.push(ps[Math.floor(ps.length * i / 10)]);
    function dec(p) {
      for (var i = 0; i < cuts.length; i++) if (p < cuts[i]) return i;
      return 9;
    }
    function gaps(keyFn, minN) {
      var g = {};
      B.forEach(function (b) {
        var k = keyFn(b);
        if (k == null) return;
        (g[k] = g[k] || { W: [], T: [] })[b.t === '公寓' ? 'W' : 'T'].push(b.y);
      });
      var out = [];
      Object.keys(g).forEach(function (k) {
        var v = g[k];
        if (v.W.length >= minN && v.T.length >= minN) out.push(medianOf(v.W) - medianOf(v.T));
      });
      return out;
    }
    var byPrice = gaps(function (b) { return dec(b.p); }, 25);
    var priceNeg = byPrice.filter(function (x) { return x < 0; }).length;
    var byDist = gaps(function (b) { return b.c + '|' + b.d; }, 10);
    if (!byPrice.length || !byDist.length) return null;
    return {
      price: medianOf(byPrice), nPrice: byPrice.length, priceNeg: priceNeg,
      dist: medianOf(byDist), nDist: byDist.length,
      distWin: byDist.filter(function (x) { return x > 0; }).length,
    };
  }

  function secDead() {
    var dh = D.dead_hypothesis;
    var wc = walkupControls();
    var share = dh.cost_share_pct != null ? Math.round(dh.cost_share_pct)
              : (dh.net_gap ? Math.round((1 - dh.gross_gap / dh.net_gap) * 100) : 0);
    // The verdict is derived in the build, not written here. It used to be the
    // hard-coded string "dead" -- true for two cities, never re-checked when the
    // scope went national, and false there. Copy follows the data now.
    var gci = dh.gross_ci || {};
    var ciTxt = gci.lo != null
      ? ' ' + Sf('ciPP', gci.lo.toFixed(3), gci.hi.toFixed(3)) : '';
    var alive = dh.verdict === 'alive' || dh.verdict === 'reversed';
    function tbl(rows, head) {
      return '<div style="margin-bottom:var(--sp5)"><div class="hs-fig-t" style="margin-bottom:var(--sp3)">' +
        esc(head) + '</div><table style="font-size:13.5px" aria-label="' + esc(head) + '"><thead><tr>' +
        '<th style="cursor:default"></th><th style="cursor:default;text-align:right">n</th>' +
        '<th style="cursor:default;text-align:right">' + esc(S('thYield')) + '</th>' +
        '<th style="cursor:default;text-align:right">' + esc(S('thNet')) + '</th></tr></thead><tbody>' +
        rows.map(function (r) {
          return '<tr><td>' + esc(r.type ? typeLabel(r.type) : r.flag) + '</td>' +
            '<td class="num">' + n0(r.n) + '</td>' +
            '<td class="num">' + pct(r.gross) + '</td>' +
            '<td class="num">' + pct(r.net) + '</td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    return sec(alive ? 'deadEyA' : 'deadEy', alive ? 'deadHA' : 'deadH', 1,
      '<p class="hs-prose">' + esc(alive
        ? Sf('deadPA', dh.gross_gap.toFixed(3), ciTxt, dh.net_gap.toFixed(3))
        : Sf('deadP', dh.gross_gap.toFixed(2), dh.net_gap.toFixed(2), share)) + '</p>' +
      (alive ? '<p class="hs-plain">' + esc(S('deadFix')) + '</p>' : '') +
      (wc ? '<p class="hs-plain">' + esc(Sf('deadCtl',
          dh.gross_gap.toFixed(3),
          (wc.price >= 0 ? '+' : '') + wc.price.toFixed(3), wc.nPrice, wc.priceNeg,
          (wc.dist >= 0 ? '+' : '') + wc.dist.toFixed(3), wc.nDist,
          wc.distWin, wc.nDist)) + '</p>' : '') +
      '<div class="hs-vs" style="max-width:560px;margin-bottom:var(--sp6)">' +
        '<div class="hs-vs-item"><div class="hs-vs-v">' + dh.gross_gap.toFixed(2) +
          '<span style="font-size:.5em">pp</span></div><div class="hs-vs-l">' +
          esc(S('deadGross')) +
          (gci.lo != null ? '<br><span class="hs-sub2">' +
            esc(Sf('ciPP', gci.lo.toFixed(3), gci.hi.toFixed(3))) + '</span>' : '') +
          '</div></div>' +
        '<div class="hs-vs-item muted"><div class="hs-vs-v">' + dh.net_gap.toFixed(2) +
          '<span style="font-size:.5em">pp</span></div><div class="hs-vs-l">' +
          esc(S('deadNet')) + '</div></div>' +
      '</div>' +
      '<div class="hs-card">' + tbl(dh.by_type, S('byType')) + tbl(dh.by_manager, S('byMgr')) + '</div>' +
      (D.repairs_spec ? '<div style="margin-top:var(--sp6)"><h3>' + esc(S('repH')) + '</h3>' +
        '<p class="hs-prose">' + esc(Sf('repP', D.repairs_spec.flat.toFixed(2),
            D.repairs_spec.age_scaled.toFixed(2))) + '</p>' +
        '<div class="hs-vs" style="max-width:640px">' +
          '<div class="hs-vs-item"><div class="hs-vs-v">' + D.repairs_spec.gross.toFixed(2) +
            '<span style="font-size:.5em">pp</span></div><div class="hs-vs-l">' +
            esc(S('repGross')) + '</div></div>' +
          '<div class="hs-vs-item muted"><div class="hs-vs-v">' + D.repairs_spec.age_scaled.toFixed(2) +
            '<span style="font-size:.5em">pp</span></div><div class="hs-vs-l">' +
            esc(S('repAge')) + '</div></div>' +
          '<div class="hs-vs-item muted"><div class="hs-vs-v">' + D.repairs_spec.flat.toFixed(2) +
            '<span style="font-size:.5em">pp</span></div><div class="hs-vs-l">' +
            esc(S('repFlat')) + '</div></div>' +
        '</div></div>' : ''));
  }

  function secScatter() {
    var B = filtered();
    var W = 860, H = 470, padL = 62, padR = 18, padT = 18, padB = 46;
    var pw = W - padL - padR, ph = H - padT - padB;
    var xmax = 170, ymax = 45000;
    var X = function (v) { return padL + (v / 10000) / xmax * pw; };
    var Y = function (v) { return padT + ph - v / ymax * ph; };
    var inRange = B.filter(function (b) { return b.p / 10000 <= xmax && b.r <= ymax; });
    var dropped = B.length - inRange.length;
    var grid = '';
    ticks(0, xmax, 8).forEach(function (t) {
      grid += line(X(t * 10000), padT, X(t * 10000), padT + ph, 'var(--grid)', 1) +
        txt(X(t * 10000), H - 26, Math.round(t), 'hs-axis', 'middle',
            ' style="fill:var(--muted);font-size:11px"');
    });
    ticks(0, ymax, 6).forEach(function (t) {
      grid += line(padL, Y(t), padL + pw, Y(t), 'var(--grid)', 1) +
        txt(padL - 8, Y(t) + 4, (t / 1000).toFixed(0) + 'k', 'hs-axis', 'end',
            ' style="fill:var(--muted);font-size:11px"');
    });
    var iso = '';
    [2, 3, 4, 5].forEach(function (y) {
      var px = xmax * 10000, py = px * y / 100;
      var cut = py > ymax ? { x: ymax / (y / 100), y: ymax } : { x: px, y: py };
      iso += line(X(0), Y(0), X(cut.x), Y(cut.y), 'var(--dim)', 1, ' stroke-dasharray="4 4"') +
        txt(X(cut.x) - 4, Y(cut.y) + (py > ymax ? 16 : -6), y + '%', 'hs-glab', 'end',
            ' style="fill:var(--subtle);font-size:11px"');
    });
    var dots = inRange.map(function (b) {
      return '<circle cx="' + X(b.p).toFixed(1) + '" cy="' + Y(b.r).toFixed(1) +
        '" r="2.6" fill="var(--text)" opacity="0.45"/>';
    }).join('');
    return sec('scatEy', null, 1,
      '<h2>' + esc(Sf('scatH', n0(B.length))) + '</h2>' +
      '<p class="hs-prose">' + esc(S('scatP')) + '</p>' + legend(TYPES) +
      '<div class="hs-card hs-scroll" id="hs-scatter" data-padl="' + padL + '" data-padt="' + padT +
        '" data-pw="' + pw + '" data-ph="' + ph + '" data-xmax="' + xmax + '" data-ymax="' + ymax + '">' +
        svg(W, H, grid + iso + dots +
          txt(padL + pw / 2, H - 6, S('scatX'), 'hs-glab', 'middle') +
          txt(-(padT + ph / 2), 14, S('scatY'), 'hs-glab', 'middle', ' transform="rotate(-90)"'),
          '', Sf('scatH', n0(D.headline.buildings)) + ' — ' + S('scatX') + ' × ' + S('scatY')) +
      '</div>' +
      (dropped ? '<div class="hs-fig-n">' + esc(Sf('scatDrop', dropped)) + '</div>' : ''));
  }

  // Net yields at the CURRENT slider settings, not the payload's defaults.
  //
  // The caption under this chart says the cost sliders move it. When first
  // written that was false: the chart read D.histogram_net, D.headline.net and
  // the precomputed b.nt, all frozen in the payload, so every slider left it
  // pixel-identical -- while the table's net column right below it did respond,
  // giving the reader every reason to believe the chart had too. Recomputed
  // through the same netYield() twin the table uses, so the sentence is true.
  function liveNets() {
    var a = asm();
    var out = [];
    (D.buildings || []).forEach(function (b) {
      var v = netYield(b, a);
      if (v != null && isFinite(v)) out.push(v);
    });
    return out;
  }
  function netBelowN(t, nets) {
    nets = nets || liveNets();
    return nets.filter(function (v) { return v < t; }).length;
  }
  function netBelowPct(t, nets) {
    nets = nets || liveNets();
    return nets.length ? netBelowN(t, nets) / nets.length * 100 : 0;
  }
  // Same bins the build uses (underwrite.histogram): 24 buckets over [lo, hi]
  // with values CLIPPED into range, so the end buckets are pile-ups.
  function histOf(vals, lo, hi, bins) {
    var w = (hi - lo) / bins, out = [];
    for (var i = 0; i < bins; i++) out.push({ x0: lo + i * w, x1: lo + (i + 1) * w, n: 0 });
    vals.forEach(function (v) {
      var c = Math.min(hi, Math.max(lo, v));
      var i = Math.min(bins - 1, Math.floor((c - lo) / w));
      out[i].n++;
    });
    return out;
  }

  // Drawn on its own so the cost sliders can redraw it without a full render.
  // The caption claims the sliders move this chart; they only actually do
  // because renderHistogram() is wired into the slider handler beside
  // renderWaterfall() and renderTable(). Making the data live was necessary and
  // not sufficient -- the first attempt recomputed correctly and still never
  // repainted, because nothing asked it to.
  function histFigure() {
    var hist = D.histogram;
    var nets = liveNets();
    // Recomputed at the current assumptions; D.histogram_net is the default-case
    // equivalent and is kept as the fallback when there are no building rows.
    var histN = nets.length ? histOf(nets, -1, 5, 24) : (D.histogram_net || []);
    // The reference rates get a label rail ABOVE the plot, one row each in
    // descending order of rate, so no label sits beside a line or another label:
    // at 375px the three lines are ~10px apart and the two medians sit within
    // 6px of the deposit line.
    var bms = (D.benchmarks || []).filter(function (b) { return b.rate != null; })
      .slice().sort(function (a, b) { return b.rate - a.rate; });
    var RAIL = 12;
    var W = chartW(420), padL = 40, padB = 34, padT = 12 + bms.length * RAIL,
        H = 210 + bms.length * RAIL;
    var maxN = Math.max.apply(null, hist.concat(histN).map(function (h) { return h.n; }));
    var lo = Math.min(hist[0].x0, histN.length ? histN[0].x0 : hist[0].x0);
    var hi = Math.max(hist[hist.length - 1].x1,
                      histN.length ? histN[histN.length - 1].x1 : hist[hist.length - 1].x1);
    var PW = W - padL - 14;
    var HX = function (v) { return padL + (v - lo) / (hi - lo) * PW; };
    var HY = function (n) { return H - padB - n / maxN * (H - padT - padB); };
    var bars = hist.map(function (h) {
      var x0 = HX(h.x0), x1 = HX(h.x1), y = HY(h.n);
      return rect(x0 + 0.6, y, Math.max(0.8, x1 - x0 - 1.2), H - padB - y, 'url(#hxbar)',
                  ' stroke="var(--text)" stroke-width=".7"');
    }).join('');
    // Net as a stepped outline, not a second fill: same solid/hollow grammar the
    // rent-bias and cost charts already use.
    var netPath = histN.length
      ? '<path d="' + histN.map(function (h, i) {
          return (i ? 'L' : 'M') + HX(h.x0).toFixed(1) + ' ' + HY(h.n).toFixed(1) +
                 ' L' + HX(h.x1).toFixed(1) + ' ' + HY(h.n).toFixed(1);
        }).join(' ') + '" fill="none" stroke="var(--text)" stroke-width="1.6" ' +
        'stroke-linejoin="round" opacity=".85"/>'
      : '';
    // ticks(lo, hi, n) takes the number of INTERVALS, not a step. Passing 1
    // here collapsed the axis to its two endpoints.
    var t0 = Math.ceil(lo), t1 = Math.floor(hi);
    var axis = ticks(t0, t1, Math.max(1, t1 - t0)).map(function (t) {
      return txt(HX(t), H - 14, t, 'hs-axis', 'middle',
        ' style="fill:var(--muted);font-size:11px"');
    }).join('');
    function medLine(v, dash) {
      return v == null ? '' : line(HX(v), padT, HX(v), H - padB, 'var(--text)', 1.5,
                                   ' stroke-dasharray="' + dash + '"');
    }
    // Solid lines with a surface-coloured halo (the gap chart's trick for its
    // circles) so they read over the hatched bars in both themes; dashes stay
    // reserved for the two medians.
    var bmLab = { deposit_1y: 'bmLDep', rediscount: 'bmLRed', mortgage: 'bmLMort' };
    var bmLines = bms.map(function (b, i) {
      var x = HX(b.rate), yTop = padT - 2 - i * RAIL;
      if (x < padL || x > W - 14) return '';
      var lab = S(bmLab[b.key] || b.key) + ' ' + bmFmt(b);
      var right = x > W - 90;
      return line(x, yTop, x, H - padB, 'var(--surface)', 3.2) +
        line(x, yTop, x, H - padB, 'var(--muted)', 1.2) +
        txt(right ? x - 3 : x + 3, yTop - 2, lab, 'hs-axis', right ? 'end' : 'start',
            ' style="fill:var(--muted);font-size:10px"');
    }).join('');
    bars = bars + netPath + axis +
      medLine(D.headline.yield, '3 3') +
      medLine(nets.length ? medianOf(nets) : D.headline.net, '1 3') + bmLines;

    return '<div class="hs-card hs-scroll">' + svg(W, H, bars, '', S('histH')) + '</div>' +
      '<div class="hs-fig-n">' + esc(S('histX')) + ' &middot; ' +
        esc(Sf('histLeg', D.headline.yield.toFixed(2),
               nets.length ? medianOf(nets).toFixed(2)
                 : (D.headline.net == null ? '--' : D.headline.net.toFixed(2)))) + '</div>' +
      (bms.length === 3 && bmOf('deposit_1y') && bmOf('rediscount') && bmOf('mortgage')
        ? '<div class="hs-fig-n">' + esc(Sf('bmLeg', bmFmt(bmOf('deposit_1y')),
            bmFmt(bmOf('rediscount')), bmFmt(bmOf('mortgage')))) + '</div>' : '') +
      '<div class="hs-fig-n">' + esc(S('histClip')) + '</div>' +
      (histN.length ? '<div class="hs-fig-n">' + esc(Sf('histNetN',
          netBelowPct(1, nets).toFixed(1), netBelowN(0, nets))) + '</div>' : '');
  }

  function renderHistogram() {
    var host = document.getElementById('hs-hist');
    if (host) host.innerHTML = histFigure();
  }

  function secMethodChecks() {
    // padT used to be declared here and shared with the histogram; it left with
    // that block when the figure was extracted, and the gap chart below still
    // reads it. The syntax check passed and the whole page threw at runtime.
    var padT = 12;
    var g = D.gap_sensitivity, W2 = chartW(420), H2 = 210, gl = 46, gb = 34;
    var glo = Math.min.apply(null, g.map(function (x) { return x.yield; })) - 0.06;
    var ghi = Math.max.apply(null, g.map(function (x) { return x.yield; })) + 0.06;
    var GX = function (i) { return gl + i / Math.max(1, g.length - 1) * (W2 - gl - 20); };
    var GY = function (v) { return padT + (1 - (v - glo) / (ghi - glo)) * (H2 - padT - gb); };
    var gsvg = ticks(glo, ghi, 3).map(function (t) {
      return line(gl, GY(t), W2 - 20, GY(t), 'var(--grid)', 1) +
        txt(gl - 8, GY(t) + 4, t.toFixed(2), 'hs-axis', 'end',
            ' style="fill:var(--muted);font-size:11px"');
    }).join('') +
      '<path d="' + g.map(function (p, i) { return (i ? 'L' : 'M') + GX(i) + ' ' + GY(p.yield); }).join(' ') +
      '" fill="none" stroke="var(--accent)" stroke-width="2"/>' +
      g.map(function (p, i) {
        return '<circle cx="' + GX(i) + '" cy="' + GY(p.yield) + '" r="4.5" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>' +
          txt(GX(i), H2 - 14, p.gap, 'hs-axis', 'middle', ' style="fill:var(--muted);font-size:11px"');
      }).join('') + txt(W2 / 2, H2 - 2, S('gapX'), 'hs-glab', 'middle', ' style="font-size:11px"');

    var idx = (D.index_test || []).map(function (r) {
      return '<tr><td class="num">&plusmn;' + r.window + '</td><td>' +
        esc(r.index === 'on' ? S('idxOn') : S('idxOff')) + '</td>' +
        '<td class="num">' +
        (r.slope >= 0 ? '+' : '') + r.slope.toFixed(3) + ' pp</td></tr>';
    }).join('');

    return sec('mcEy', 'mcH', 1,
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:32px">' +
        '<div><h3>' + esc(S('histH')) + '</h3>' +
          '<div id="hs-hist">' + histFigure() + '</div></div>' +
        '<div><h3>' + esc(S('gapH')) + '</h3>' +
          '<div class="hs-card hs-scroll">' + svg(W2, H2, gsvg, '', S('gapH')) + '</div></div>' +
      '</div>' +
      '<p class="hs-prose" style="margin-top:var(--sp5)">' + esc(S('gapP')) + '</p>' +
      '<div class="hs-card" style="max-width:460px"><div class="hs-fig-t" style="margin-bottom:var(--sp3)">' +
        esc(S('idxH')) + '</div><table style="font-size:13.5px" aria-label="' + esc(S('idxH')) + '"><thead><tr>' +
        '<th style="cursor:default;text-align:right">' + esc(S('idxWin')) + '</th>' +
        '<th style="cursor:default">' + esc(S('idxIdx')) + '</th>' +
        '<th style="cursor:default;text-align:right">' + esc(S('idxSlope')) + '</th>' +
        '</tr></thead><tbody>' + idx + '</tbody></table></div>');
  }

  function secTable() {
    return sec('tblEy', 'tblH', 0,
      '<p class="hs-prose">' + esc(S('tblP')) + '</p>' +
      '<div class="hs-controls">' +
        '<input class="hs-input" id="hs-q" type="search" placeholder="' + esc(S('search')) +
          '" value="' + esc(state.q) + '">' +
        '<button class="hs-chip" data-type="" aria-pressed="' + (!state.type) + '">' +
          esc(S('allTypes')) + '</button>' +
        TYPES.map(function (t) {
          return '<button class="hs-chip" data-type="' + esc(t) + '" aria-pressed="' +
            (state.type === t) + '">' + esc(typeLabel(t)) + '</button>';
        }).join('') +
        '<span class="hs-mono-s" id="hs-count"></span>' +
      '</div>' +
      '<div class="hs-tbl-wrap"><table aria-label="' + esc(S('tblH')) + '"><thead><tr>' +
        th('a', S('thAddr')) + th('d', S('thDist')) + th('t', S('thType')) +
        th('y', S('thYield'), 1) + th('nt', S('thNet'), 1) + th('p', S('thPrice'), 1) +
        th('r', S('thRent'), 1) + th('n', S('thPairs'), 1) + th('b', S('thBuilt'), 1) +
      '</tr></thead><tbody id="hs-tbody"></tbody></table></div>');
  }
  function th(k, label, right) {
    var on = state.sort === k;
    return '<th data-sort="' + k + '"' + (on ? ' aria-sort="' + (state.desc ? 'descending' : 'ascending') + '"' : '') +
      (right ? ' style="text-align:right"' : '') + '>' + esc(label) +
      (on ? (state.desc ? ' ↓' : ' ↑') : '') + '</th>';
  }

  function renderTable() {
    var body = document.getElementById('hs-tbody');
    if (!body) return;
    var a = asm();
    var rows = filtered().slice();
    var k = state.sort, desc = state.desc;
    rows.sort(function (x, y) {
      var p = k === 'nt' ? netYield(x, a) : x[k], q = k === 'nt' ? netYield(y, a) : y[k];
      if (typeof p === 'string') return desc ? q.localeCompare(p) : p.localeCompare(q);
      p = p == null ? -1e9 : p; q = q == null ? -1e9 : q;
      return desc ? q - p : p - q;
    });
    body.innerHTML = rows.slice(0, 600).map(function (b) {
      var ny = netYield(b, a);
      return '<tr>' +
        '<td>' + typeMark(b.t, 11) + esc(b.a) + '</td>' +
        '<td>' + esc(b.d) + '</td><td>' + esc(typeLabel(b.t)) + '</td>' +
        '<td class="num">' + b.y.toFixed(2) + '%</td>' +
        '<td class="num" style="color:var(--muted)">' + (ny == null ? '--' : ny.toFixed(2) + '%') + '</td>' +
        '<td class="num">' + money(b.p) + '</td>' +
        '<td class="num">' + n0(b.r) + '</td>' +
        '<td class="num">' + b.n + '</td>' +
        '<td class="num">' + (b.b == null ? '--' : b.b) + '</td></tr>';
    }).join('');
    var c = document.getElementById('hs-count');
    if (c) c.textContent = Sf('showing', n0(rows.length)) + (rows.length > 600 ? ' (top 600)' : '');
  }

  // 內政部's own figures beside this site's. Simple mode, because the pairing
  // is the argument: the official number, ours, and the gap between them --
  // and the gap is the same finding every other section reaches from inside
  // the registry, now reached from outside it.
  function secMoi() {
    var m = D.moi;
    if (!m || (!m.auction && !m.stock && !m.price)) return '';
    var html = '<p class="hs-prose">' + esc(S('moiP')) + '</p>';

    // the denominator behind the denominator
    if (m.stock && m.ours) {
      var bs = m.stock.building_stock, hs = m.stock.housing_stock;
      var cards = '';
      if (bs) {
        cards += '<div class="hs-vs-item"><div class="hs-vs-v">' + n0(bs.value) + '</div>' +
          '<div class="hs-vs-l">' + esc(LANG === 'zh' ? bs.zh : bs.en) +
          '<br><span class="hs-sub2">' + esc(bs.unit) + ' · ' + esc(bs.period) + '</span></div></div>';
      }
      cards += '<div class="hs-vs-item muted"><div class="hs-vs-v">' + n0(m.ours.universe_buildings) + '</div>' +
        '<div class="hs-vs-l">' + esc(S('moiUniv')) + '</div></div>' +
        '<div class="hs-vs-item" style="color:var(--accent)"><div class="hs-vs-v">' + n0(m.ours.matched_buildings) + '</div>' +
        '<div class="hs-vs-l">' + esc(S('moiMatched')) + '</div></div>';
      html += '<h3>' + esc(S('moiStockH')) + '</h3><div class="hs-vs">' + cards + '</div>';
      // This used to divide 9,805 buildings by 建物總量 and print "one building
      // in 1,086". 建物總量 counts 建號 -- it EXCEEDS the dwelling count in every
      // county, which no physical-building count could -- so the ratio compared
      // buildings to units and was wrong by an unknown multiple. Withdrawn.
      html += '<p class="hs-plain">' + esc(LANG === 'zh' ? m.ours.no_ratio_zh : m.ours.no_ratio_en) + '</p>' +
        '<p class="hs-fig-n hs-prose">' + esc(Sf(MODE === 'advanced' ? 'moiStockN2' : 'moiStockN3',
            hs ? n0(hs.value) : '?', hs ? hs.period : '?',
            m.stock.resi_tax_roll ? n0(m.stock.resi_tax_roll.value) : '?',
            m.stock.resi_tax_roll ? m.stock.resi_tax_roll.period : '?')) + '</p>';
    }

    // the price check
    if (m.price && m.price.rows && m.price.rows.length) {
      var rows = m.price.rows.map(function (r) {
        return '<tr><td>' + esc(r.city) + '</td>' +
          '<td class="num">' + n0(r.official) + '</td>' +
          '<td class="num">' + n0(r.ours) + '</td>' +
          '<td class="num" style="font-weight:600">' + (r.gap_pct >= 0 ? '+' : '') + r.gap_pct.toFixed(1) + '%</td>' +
          '<td class="num">' + n0(r.n) + '</td></tr>';
      }).join('');
      var big = m.price.rows.filter(function (r) { return r.n >= 500; });
      var medGap = big.length ? medianOf(big.map(function (r) { return r.gap_pct; })) : null;
      html += '<h3>' + esc(S('moiPriceH')) + '</h3>' +
        '<p class="hs-prose">' + esc(Sf('moiPriceP', m.price.period)) + '</p>' +
        '<div class="hs-scroll"><table style="font-size:13.5px" aria-label="' + esc(S('moiPriceH')) + '"><thead><tr>' +
          '<th style="cursor:default"></th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiOfficial')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiOurs')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiGap')) + '</th>' +
          '<th style="cursor:default;text-align:right">n</th></tr></thead><tbody>' +
          rows + '</tbody></table></div>' +
        // (count, gap) -- both strings take them in that order. Passed the
        // other way round this rendered "+9.8 counties ... 6%".
        (medGap != null ? '<p class="hs-plain">' + esc(Sf('moiPriceWhy',
            big.length, (medGap >= 0 ? '+' : '') + medGap.toFixed(1))) + '</p>' : '') +
        '<p class="hs-fig-n hs-prose">' + esc(LANG === 'zh' ? m.price.note_zh : m.price.note_en) + '</p>';
    }

    // 法拍 beside 金拍 -- advanced only. A first-time reader is not buying at
    // auction, and the block cited a section that simple mode does not show.
    if (MODE === 'advanced' && m.auction && m.auction.court_lots) {
      var a = m.auction;
      html += '<h3>' + esc(S('moiAucH')) + '</h3>' +
        '<div class="hs-vs" style="max-width:640px">' +
          '<div class="hs-vs-item"><div class="hs-vs-v">' + n0(a.court_lots) + '</div>' +
            '<div class="hs-vs-l">' + esc(S('moiCourt')) + '</div></div>' +
          '<div class="hs-vs-item muted"><div class="hs-vs-v">' + n0(a.fasc_lots) + '</div>' +
            '<div class="hs-vs-l">' + esc(S('moiFasc')) + '</div></div>' +
        '</div>' +
        '<p class="hs-prose">' + esc(Sf(a.fasc_windowed ? 'moiAucP' : 'moiAucP0', n0(a.court_lots), a.quarters,
            a.court_value != null ? (a.court_value / 1e8).toFixed(0) : '?',
            n0(a.fasc_lots), a.fasc_vs_court_pct != null ? a.fasc_vs_court_pct.toFixed(0) : '?')) + '</p>' +
        (a.by_county && a.by_county.length ? '<p class="hs-fig-n hs-prose">' + esc(Sf('moiAucTop',
            a.by_county.slice(0, 5).map(function (r) { return r.city + ' ' + n0(r.lots); }).join('、'))) + '</p>' : '');
    }

    // the official index against the drift this site leaves in
    if (m.price_index && m.price_index.drift_at_median_gap_pct != null) {
      var pi = m.price_index;
      html += '<h3>' + esc(S('moiIdxH')) + '</h3>' +
        '<div class="hs-vs" style="max-width:640px">' +
          '<div class="hs-vs-item"><div class="hs-vs-v">' + (pi.total_pct >= 0 ? '+' : '') + pi.total_pct.toFixed(1) + '%</div>' +
            '<div class="hs-vs-l">' + esc(Sf('moiIdxWin', pi.start.period, pi.end.period)) + '</div></div>' +
          '<div class="hs-vs-item muted"><div class="hs-vs-v">' + (pi.drift_at_median_gap_pct >= 0 ? '+' : '') + pi.drift_at_median_gap_pct.toFixed(2) + '%</div>' +
            '<div class="hs-vs-l">' + esc(Sf('moiIdxDrift', pi.median_pair_gap_q.toFixed(1))) + '</div></div>' +
        '</div>' +
        '<p class="hs-prose">' + esc(Sf('moiIdxP', pi.start.value.toFixed(2), pi.end.value.toFixed(2),
            pi.quarters, pi.per_quarter_pct.toFixed(2), pi.median_pair_gap_q.toFixed(1),
            pi.drift_at_median_gap_pct.toFixed(2))) + '</p>';
    }

    // empty homes, beside the vacancy assumption -- context, not an input
    if (m.low_use && m.low_use.rows && m.low_use.rows.length) {
      var lu = m.low_use;
      var nat = lu.rows.filter(function (r) { return r.county === 'all'; })[0];
      var cty = lu.rows.filter(function (r) { return r.county !== 'all'; })
        .sort(function (a, b) { return b.rate_pct - a.rate_pct; });
      var lrows = cty.map(function (r) {
        return '<tr><td>' + esc(r.city) + '</td>' +
          '<td class="num">' + n0(r.low_use) + '</td>' +
          '<td class="num">' + n0(r.stock) + '</td>' +
          '<td class="num" style="font-weight:600">' + r.rate_pct.toFixed(1) + '%</td></tr>';
      }).join('');
      var vb = D.vacancy_breakeven;
      html += '<h3>' + esc(S('moiLuH')) + '</h3>' +
        '<p class="hs-prose">' + esc(Sf('moiLuP', lu.period, nat ? nat.rate_pct.toFixed(1) : '?',
            lu.site_vacancy_pct.toFixed(0))) + '</p>' +
        '<div class="hs-scroll"><table style="font-size:13.5px" aria-label="' + esc(S('moiLuH')) + '"><thead><tr>' +
          '<th style="cursor:default"></th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiLuN')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiLuStock')) + '</th>' +
          '<th style="cursor:default;text-align:right">' + esc(S('moiLuRate')) + '</th></tr></thead><tbody>' +
          lrows + '</tbody></table></div>' +
        // Sf, not S: the string carries %% and only Sf collapses it to %.
        '<p class="hs-plain">' + esc(Sf('moiLuWhy')) + '</p>' +
        (vb && vb.breakeven_vacancy_pct != null && vb.city ? (function () {
          var row = cty.filter(function (r) { return r.city === vb.city; })[0];
          return row ? '<p class="hs-fig-n hs-prose">' + esc(Sf('moiLuVb',
              vb.city, vb.district, vb.breakeven_vacancy_pct.toFixed(1),
              vb.city, row.rate_pct.toFixed(1))) + '</p>' : '';
        })() : '');
    }

    if (MODE === 'advanced' && m.unsold_new) {
      html += '<p class="hs-fig-n hs-prose">' + esc(Sf('moiUnsold',
          n0(m.unsold_new.value), m.unsold_new.period)) + '</p>';
    }

    if (MODE === 'advanced' && m.mortgage && D.mortgage) {
      html += '<p class="hs-fig-n hs-prose">' + esc(Sf('moiMort',
          m.mortgage.rate.toFixed(2), m.mortgage.period,
          D.mortgage.rate.toFixed(3), LANG === 'zh' ? D.mortgage.period_zh : D.mortgage.period_en)) + '</p>';
    }
    html += '<p class="hs-fig-n hs-prose">' + esc(LANG === 'zh' ? m.source_zh : m.source_en) + '</p>';
    return sec('moiEy', 'moiH', 0, html);
  }

  function secLimits() {
    var m = D.meta, h = D.headline;
    var items = [Sf('lim1', h.coverage_pct), Sf('lim2', m.n_seasons, m.seasons[0], m.seasons[1]),
                 Sf('lim3', ((D.rent_bias && D.rent_bias.social_share_pct) || 0).toFixed(1)),
                 S('lim4')];
    if (D.partial_id && D.partial_id.rungs) {
      var PR = {}; D.partial_id.rungs.forEach(function (r) { PR[r.key] = r; });
      var hd = PR[D.partial_id.headline_rung];
      if (hd && PR.band) items.push(Sf('lim7', D.partial_id.scope.coverage_pct.toFixed(2),
        hd.gross.lo.toFixed(2), hd.gross.hi.toFixed(2),
        PR.band.gross.lo.toFixed(2), PR.band.gross.hi.toFixed(2), h.yield.toFixed(2)));
    }
    if (D.vacancy_prior && D.vacancy_prior.cases) {
      var VC = {}; D.vacancy_prior.cases.forEach(function (c) { VC[c.key] = c; });
      if (VC.flat && VC.level && VC.flat.net != null) {
        items.push(Sf('lim8', D.vacancy_prior.prior_pct.toFixed(2),
          D.vacancy_prior.national_pct.toFixed(2), VC.flat.net.toFixed(2),
          VC.level.net.toFixed(2)));
      }
    }
    if (D.walkup_resolution && D.walkup_resolution.precision) {
      items.push(Sf('lim6', D.walkup_resolution.precision.gross_gap.toFixed(2)));
    }
    if (D.parking_audit && D.parking_audit.treatments) {
      var T5 = {}; D.parking_audit.treatments.forEach(function (t) { T5[t.case] = t; });
      if (T5.area_only && T5.drop && T5.impute) items.push(Sf('lim5', D.parking_audit.lets.unpriced_pct.toFixed(1),
        T5.impute.gross.toFixed(2), T5.area_only.gross.toFixed(2), T5.drop.gross.toFixed(2), n0(-T5.drop.buildings_delta)));
    }
    return sec('limEy', 'limH', 0,
      '<div class="hs-prose">' + items.map(function (t) {
        return '<div class="hs-plain" style="margin-bottom:var(--sp4)">' + esc(t) + '</div>';
      }).join('') + '</div>');
  }

  function secMethod() {
    var m = D.meta;
    var pv = m.provenance;
    var rows = [[S('src'), S('srcV')], [S('lic'), m.licence],
                [S('win'), Sf('winV', m.seasons[0], m.seasons[1], m.n_seasons)],
                [S('addrOk'), Sf('addrOkV', m.addr ? m.addr.no_key_pct : 0)],
                [S('whyWin'), S('whyWinV')]];
    // Provenance. 實價登錄 gains a season every quarter, so a number without a
    // pinned snapshot behind it is not checkable -- someone rebuilding in six
    // months cannot tell a bug from newer data. These four rows are the fixed
    // point they compare against.
    if (pv) {
      rows.push([S('pvVer'), 'v' + pv.version + '  ·  ' + pv.built +
                             (pv.commit ? '  ·  ' + pv.commit : '')]);
      if (pv.source && pv.source.sha256) {
        rows.push([S('pvSrc'), pv.source.sha256]);
        rows.push([S('pvFiles'), Sf('pvFilesV',
          pv.source.files.filter(function (f) { return f.sha256; }).length,
          (pv.source.files.reduce(function (a, f) { return a + f.bytes; }, 0) / 1e6).toFixed(0))]);
      }
      rows.push([S('pvRepro'), S('pvReproV')]);
    }
    return sec('methEy', 'methH', 1,
      '<div class="hs-prose">' +
        '<dl class="hs-kv" style="margin-bottom:var(--sp5)">' + rows.map(function (r) {
          return '<dt>' + esc(r[0]) + '</dt><dd>' + esc(r[1]) + '</dd>';
        }).join('') + '</dl>' +
        '<h3>' + esc(S('filters')) + '</h3>' +
        '<ul style="color:var(--text2);padding-left:20px;font-size:14.5px">' +
          ['f1', 'f2', 'f3', 'f4', 'f5', 'f6'].map(function (k) {
            return '<li style="margin-bottom:8px">' + esc(S(k)) + '</li>';
          }).join('') + '</ul>' +
        '<div class="hs-callout"><p style="font-size:13.5px">' + esc(S('legal')) + '</p></div>' +
      '</div>');
  }

  // section wrapper: numbering is applied at render time, per mode
  var _n = 0;
  function sec(eyebrowKey, headKey, adv, inner) {
    _n++;
    return '<section class="hs-sec" data-adv="' + adv + '"' +
      (adv ? ' data-advlabel="' + esc(S('advOnly')) + '"' : '') + '><div class="hs-wrap">' +
      '<div class="hs-eyebrow" data-n="' + String(_n).padStart(2, '0') + '"' +
      (adv ? ' data-advlabel="' + esc(S('advOnly')) + '"' : '') + '>' + esc(S(eyebrowKey)) + '</div>' +
      (headKey ? '<h2>' + esc(S(headKey)) + '</h2>' : '') + inner + '</div></section>';
  }
  function fig(title, sub, body, extra) {
    // The chart inside gets the figure's title as its accessible name. Every
    // chart on this page is hand-drawn SVG; without this a screen reader
    // announced "image" seventeen times and nothing else.
    var name = title + (sub ? ' — ' + sub : '');
    body = body.replace('aria-hidden="true"', 'role="img" aria-label="' + esc(name) + '"');
    return '<figure class="hs-fig"><figcaption><div class="hs-fig-h"><span class="hs-fig-t">' + esc(title) +
      '</span></div>' + (sub ? '<div class="hs-fig-s">' + esc(sub) + '</div>' : '') + '</figcaption>' +
      (extra || '') + '<div class="hs-card hs-scroll">' + body + '</div></figure>';
  }

  // ══════════════════════════════════════════════════ RENDER ════════════
  // Chart hatch. Lives at page level rather than inside a section because
  // several sections reference it and most of them are advanced-mode only —
  // a section-scoped <defs> makes the fill depend on render order.
  // Outside the map the user unit is a pixel, so this tile is a literal size.
  function chartDefs() {
    return '<svg width="0" height="0" aria-hidden="true" focusable="false" ' +
      'style="position:absolute">' +
      '<defs><pattern id="hxbar" width="4.4" height="6" patternUnits="userSpaceOnUse" ' +
      'patternTransform="rotate(28)"><line x1="0" y1="0" x2="0" y2="6" ' +
      'stroke="var(--text)" stroke-width="1.5"/></pattern>' +
      '<pattern id="hxbarL" width="8" height="6" patternUnits="userSpaceOnUse" ' +
      'patternTransform="rotate(28)"><line x1="0" y1="0" x2="0" y2="6" ' +
      'stroke="var(--text)" stroke-width="1"/></pattern>' +
      // 住宅大樓 — hatch
      '<pattern id="hxt1" width="5" height="6" patternUnits="userSpaceOnUse" ' +
      'patternTransform="rotate(28)"><line x1="0" y1="0" x2="0" y2="6" ' +
      'stroke="var(--text)" stroke-width="1.3"/></pattern>' +
      // 華廈 — cross
      '<pattern id="hxt2" width="6" height="6" patternUnits="userSpaceOnUse" ' +
      'patternTransform="rotate(28)"><line x1="0" y1="0" x2="0" y2="6" ' +
      'stroke="var(--text)" stroke-width="1"/>' +
      '<line x1="0" y1="0" x2="6" y2="0" stroke="var(--text)" stroke-width="1"/></pattern>' +
      // 公寓 — stipple
      '<pattern id="hxt3" width="5" height="5" patternUnits="userSpaceOnUse">' +
      '<circle cx="1.4" cy="1.4" r="1" fill="var(--text)"/>' +
      '<circle cx="3.9" cy="3.9" r=".8" fill="var(--text)"/></pattern>' +
      '</defs></svg>';
  }

  // The <html lang> attribute stayed at zh-Hant no matter which language was on
  // screen, so a screen reader announced the English page in a Chinese voice
  // (and vice versa). It is set wherever LANG is, not once at load.
  function syncLangAttr() {
    try {
      document.documentElement.lang = LANG === 'zh' ? 'zh-Hant' : 'en';
    } catch (e) {}
  }

  function render(root) {
    syncLangAttr();
    _n = 0;
    var adv = MODE === 'advanced';
    // secMRT sits after the district ranking on purpose: the map and the
    // ranking both leave the reader asking "so what makes one area's yield
    // higher?", and this is the one answer the payload can actually support.
    // secVolume sits between 預售屋 and 借錢的成本: the first count section, using
    // the existing/presale split the reader has just been taught, before the
    // rates that follow.
    var parts = [secHero(), secCoverage(), secPartialId(), secMap(), secDistrict(), secMRT(),
                 secPresale(), secVolume(), secMortgage(), secIncome(), secWithin(),
                 secParking()];
    if (adv) parts.push(secPostStrat(), secDispersion(), secLadder(), secBias(),
                        secNet(), secDead(), secWalkup(), secAuction(), secScatter(),
                        secMethodChecks());
    parts.push(secMoi(), secTable(), secLimits());
    if (adv) parts.push(secMethod());

    root.innerHTML =
      chartDefs() +
      '<nav class="hs-top" aria-label="' + esc(S('navAria')) + '"><div class="hs-top-in">' +
        '<span class="hs-brand">' + esc(S('brand')) + '<span>' + esc(S('brandsub')) + '</span></span>' +
        '<span class="hs-top-sp"></span>' +
        '<span class="hs-seg" role="group">' +
          '<button data-mode="simple" aria-pressed="' + (!adv) + '">' + esc(S('simple')) + '</button>' +
          '<button data-mode="advanced" aria-pressed="' + adv + '">' + esc(S('advanced')) + '</button>' +
        '</span>' +
        '<button class="hs-btn" id="hs-lang">' + esc(S('en')) + '</button>' +
        '<button class="hs-btn" id="hs-theme">' + esc(S('theme')) + '</button>' +
      '</div></nav>' +
      '<main>' + parts.join('') + '</main>' +
      '<footer class="hs-foot"><div class="hs-wrap hs-prose"><p>' + esc(S('footNote')) +
        '</p><p class="hs-mono-s" style="margin-top:8px">' + esc(D.meta.generated_from) +
        ' &middot; ' + esc(D.meta.licence) +
        (D.meta.provenance
          ? '<br>' + esc(Sf('pvCite', D.meta.provenance.version,
              D.meta.provenance.built,
              (D.meta.provenance.source && D.meta.provenance.source.sha256 || '').slice(0, 12))) +
            ' &middot; <a href="housing_report.pdf">' + esc(S('pvPdf')) + '</a>' +
            ' &middot; <a href="housing_data.json.sha256">' + esc(S('pvSha')) + '</a>'
          : '') +
        '</p></div></footer>' +
      '<div class="hs-tip" id="hs-tip"></div>';
    tip = document.getElementById('hs-tip');
    renderTable();
    renderWaterfall();
    wire(root);
  }

  // Delegated listeners bind to #hs-root, which SURVIVES a re-render (only its
  // innerHTML is replaced). Re-binding them per render stacked one listener per
  // render, so a single click ran the handler N times -- and any handler that
  // FLIPS state (_layers[k] = !_layers[k], state.desc) landed back where it
  // started on an even count. Bind exactly once.
  var _bound = false;

  function wire(root) {
    wirePerRender();
    if (_bound) return;
    _bound = true;
    root.addEventListener('click', function (e) {
      var t = e.target.closest('[data-rung]');
      if (t) return setRung(+t.getAttribute('data-rung'));
      var md = e.target.closest('[data-mode]');
      if (md) {
        MODE = md.getAttribute('data-mode');
        try { localStorage.setItem('hs-mode', MODE); } catch (x) {}
        return rerender(true);
      }
      var d = e.target.closest('[data-d]');
      if (d) {
        var v = d.getAttribute('data-d');
        state.district = state.district === v ? null : v;
        return rerender();
      }
      var rk = e.target.closest('[data-rank]');
      if (rk) {
        _rankCounty = rk.getAttribute('data-rank') || null;
        // Opening a county in the ranking must not leave a district filter from
        // some other county applied to every chart below it.
        if (state.district && state.district.split('|')[0] !== _rankCounty) {
          state.district = null;
        }
        return rerender();
      }
      var c = e.target.closest('[data-dist]');
      if (c) { state.district = c.getAttribute('data-dist') || null; return rerender(); }
      var ty = e.target.closest('[data-type]');
      if (ty) { state.type = ty.getAttribute('data-type') || null; return rerender(); }
      var vc = e.target.closest('[data-vol]');
      if (vc) { state.volCounty = vc.getAttribute('data-vol') || null; return rerender(); }
      var s = e.target.closest('[data-sort]');
      if (s) {
        var k = s.getAttribute('data-sort');
        if (state.sort === k) state.desc = !state.desc;
        else { state.sort = k; state.desc = ['a', 'd', 't'].indexOf(k) < 0; }
        return rerender();
      }
      if (e.target.closest('[data-panel="close"]')) return closePanel();
      var fb = e.target.closest('#hs-filtbtn');
      if (fb) {
        var fm = document.getElementById('hs-filtmenu');
        var fo = fm.hasAttribute('hidden');
        if (fo) fm.removeAttribute('hidden'); else fm.setAttribute('hidden', '');
        fb.setAttribute('aria-expanded', String(fo));
        return;
      }
      if (e.target.closest('[data-filter="clear"]')) {
        state.maxPrice = state.minYield = state.maxMrt = null;
        return rerender();
      }
      var lb = e.target.closest('#hs-laybtn');
      if (lb) {
        var mn = document.getElementById('hs-laymenu');
        var open = mn.hasAttribute('hidden');
        if (open) mn.removeAttribute('hidden'); else mn.setAttribute('hidden', '');
        lb.setAttribute('aria-expanded', String(open));
        return;
      }
      if (!e.target.closest('.hs-lay')) {
        var mn2 = document.getElementById('hs-laymenu');
        if (mn2 && !mn2.hasAttribute('hidden')) {
          mn2.setAttribute('hidden', '');
          var lb2 = document.getElementById('hs-laybtn');
          if (lb2) lb2.setAttribute('aria-expanded', 'false');
        }
      }
      var gt = e.target.closest('[data-goto]');
      if (gt) {
        var secs = document.querySelectorAll('.hs-sec');
        if (secs[0]) secs[0].scrollIntoView({ block: 'start', behavior: 'smooth' });
        return;
      }
      var ly = e.target.closest('[data-layer]');
      if (ly) {
        var lk = ly.getAttribute('data-layer');
        _layers[lk] = !_layers[lk];
        return rerender();
      }
      if (e.target.id === 'hs-asmreset') {
        state.asm = null;
        return rerender();
      }
      if (e.target.id === 'hs-vshape') {
        state.vshape = !state.vshape;
        return rerender();
      }
      if (e.target.id === 'hs-lang') {
        LANG = LANG === 'zh' ? 'en' : 'zh';
        try { localStorage.setItem('hs-lang', LANG); } catch (x) {}
        return rerender();
      }
      if (e.target.id === 'hs-theme') {
        var cur = document.documentElement.getAttribute('data-theme');
        var next = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('hs-theme', next); } catch (x) {}
        return;   // colours are CSS variables: no re-render needed
      }
    });
    root.addEventListener('input', function (e) {
      var q = e.target.closest('#hs-q');
      if (q) { state.q = q.value.trim(); return renderTable(); }
      var fs = e.target.closest('[data-filter]');
      if (fs && fs.tagName === 'SELECT') {
        var v = fs.value === '' ? null : parseFloat(fs.value);
        state[fs.getAttribute('data-filter')] = v;
        return rerender();
      }
      var el = e.target.closest('[data-asm]');
      if (!el) return;
      var k = el.getAttribute('data-asm');
      asm()[k] = parseFloat(el.value);
      var lab = document.querySelector('[data-asmv="' + k + '"]');
      if (lab) lab.textContent = el.value;
      renderWaterfall();
      renderTable();
      renderHistogram();
      // Those three are the only surfaces that recompute. Everything else that
      // prints a net yield -- the mortgage tile, the benchmark strip, and the
      // prose that differences them against a reference rate -- reads the
      // published headline, so after a slider move the page showed two
      // different numbers under the same label. Re-render the whole thing,
      // debounced so a drag does not rebuild the map on every input event.
      clearTimeout(_asmT);
      _asmT = setTimeout(function () { rerender(); }, 260);
    });
  }
  var _asmT = null;

  // Re-bound every render: these attach to elements that the render replaces,
  // so their listeners are discarded with the old nodes and cannot stack.
  function wirePerRender() {
    wireScatter();
    wireDistrict();
    wireMap();
  }

  function setRung(i) {
    var r = D.ladder[i];
    if (!r) return;
    state.rung = i;
    var fig = document.getElementById('hs-fig');
    var cap = document.getElementById('hs-figcap');
    // Same unit as the rendered ladder, or clicking a rung shows a number
    // that is not the one printed on it.
    var rv = r.yield_building != null ? r.yield_building : r.yield;
    if (fig) fig.textContent = rv.toFixed(2) + '%';
    if (cap) cap.textContent = (LANG === 'zh' ? r.zh : r.en) + ' · ' +
      n0(r.buildings) + ' ' + S('rungBldgs');
    Array.prototype.forEach.call(document.querySelectorAll('.hs-rung'), function (el, j) {
      el.setAttribute('aria-current', j === i ? 'true' : 'false');
    });
  }

  function wireDistrict() {
    var host = document.getElementById('hs-dist');
    if (!host) return;
    host.addEventListener('mousemove', function (e) {
      var g = e.target.closest('[data-d]');
      if (!g) return tipHide();
      var name = g.getAttribute('data-d');
      var d = D.districts.filter(function (x) { return x.district === name; })[0];
      if (!d) return;
      tipShow('<b>' + esc(d.city) + esc(d.district) + '</b>' +
        kv(S('thYield'), pct(d.yield)) + kv(S('thNet'), pct(d.net)) +
        kv(S('thPrice'), money(d.price_ping)) + kv(S('thRent'), n0(d.rent_ping_yr)) +
        kv(S('sBuildings'), n0(d.buildings)), e.clientX, e.clientY);
    });
    host.addEventListener('mouseleave', tipHide);
  }

  function wireScatter() {
    var host = document.getElementById('hs-scatter');
    if (!host) return;
    var sv = host.querySelector('svg');
    host.addEventListener('mousemove', function (e) {
      var r = sv.getBoundingClientRect();
      var scale = r.width / sv.viewBox.baseVal.width;
      var padL = +host.dataset.padl, padT = +host.dataset.padt;
      var pw = +host.dataset.pw, ph = +host.dataset.ph;
      var xmax = +host.dataset.xmax, ymax = +host.dataset.ymax;
      var mx = (e.clientX - r.left) / scale, my = (e.clientY - r.top) / scale;
      var B = filtered(), best = null, bd = 14 * 14;
      for (var i = 0; i < B.length; i++) {
        var b = B[i];
        if (b.p / 10000 > xmax || b.r > ymax) continue;
        var px = padL + (b.p / 10000) / xmax * pw;
        var py = padT + ph - b.r / ymax * ph;
        var dd = (px - mx) * (px - mx) + (py - my) * (py - my);
        if (dd < bd) { bd = dd; best = b; }
      }
      if (!best) return tipHide();
      var ny = netYield(best);
      tipShow('<b>' + esc(best.a) + '</b>' + kv(S('thType'), typeLabel(best.t)) +
        kv(S('thYield'), pct(best.y)) + kv(S('thNet'), ny == null ? '--' : pct(ny)) +
        kv(S('thPrice'), money(best.p)) + kv(S('thPairs'), best.n), e.clientX, e.clientY);
    });
    host.addEventListener('mouseleave', tipHide);
  }

  function rerender(toTop) {
    var root = document.getElementById('hs-root');
    var y = window.scrollY;
    render(root);
    window.scrollTo(0, toTop ? 0 : y);
  }

  // ══════════════════════════════════════════════════ BOOT ══════════════
  function boot() {
    var root = document.getElementById('hs-root');
    if (!root) return;
    try {
      LANG = localStorage.getItem('hs-lang') || 'zh';
      MODE = localStorage.getItem('hs-mode') || 'simple';
    } catch (e) {}
    root.innerHTML = '<div class="hs-wrap" style="padding:80px 24px;color:var(--muted)">' +
      S('loading') + '</div>';
    fetch('housing_data.json')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { D = j; render(root); })
      .catch(function (err) {
        root.innerHTML = '<div class="hs-wrap" style="padding:80px 24px">' +
          '<h2>' + esc(S('failed')) + '</h2><p class="hs-mono-s">' + esc(String(err)) + '</p></div>';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }

  window.QHousing = {
    rerender: rerender,
    data: function () { return D; },
    netYield: netYield,
    mode: function (m) { if (m) { MODE = m; rerender(true); } return MODE; }
  };
})();
