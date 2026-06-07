import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiFetch, ensureDevSession } from '../api/apiClient'
import type { MockPurchaseResponse } from '../types/billing'

type Lang = 'zh' | 'en'

const content = {
  zh: {
    // Header
    backToDashboard: '返回 Dashboard',

    // Hero
    heroTag: '灵活的额度 · 透明的价格',
    heroTitle: '选择适合你的学习套餐',
    heroDesc: '从轻度体验到重度创作，找到最匹配你的方案。所有套餐均支持 8 种语言与高质量学习卡生成。',

    // Monthly plans
    monthlyTitle: '月度订阅套餐',
    monthlyBadge: '推荐长期使用',

    // Plan field labels
    monthlyQuotaLabel: '月度处理额度',
    narrationQuotaLabel: '月度解说额度',
    singleLimitLabel: '单次视频限制',
    dailyLimitLabel: '单日处理上限',
    targetLabel: '目标用户',

    // Buttons
    subscribePro: '立即订阅 Pro',
    choosePlan: '选择此套餐',

    // Plans footer
    plansFooter: '所有套餐均包含：8 种语言支持 · 自动生成场景学习卡 · 基础解说额度 · 学习卡永久保留',

    // Addons
    addonsTitle: '额外付费 · 额度包',
    addonsSubtitle:
      '解说包按分钟数同时补充处理与解说额度；仅需处理时可单独购买视频处理包',
    buyNow: '立即购买',

    // Footer
    tipsTitle: '温馨提示',
    tip1: '生成的视频文件在您下载一次后会按策略自动清理，学习卡长期保留。',
    tip2:
      '处理额度按实际处理时长扣除；开启解说声道时，解说额度同步扣除。解说包所含处理额度与解说额度分钟数相同。',
    tip3: '当前为 Beta 定价阶段，欢迎通过「Contact Support」反馈您的使用体验。',

    // Free plan
    startFree: '开始免费使用',
    freeBadge: '默认套餐',

    // Mock purchase modal
    mockPayTitle: '模拟付费确认',
    mockPayBeta: 'Beta 模拟支付，不会产生真实扣款。',
    mockPayItem: '商品',
    mockPayPrice: '价格',
    mockPayAdds: '将增加额度',
    mockPayProcessing: '基础处理',
    mockPayNarration: '解说',
    mockPayMinutes: '分钟',
    mockPayPlanNote: '确认后将切换至该套餐，并立即增加对应月度额度。',
    mockPayCancel: '取消',
    mockPayConfirm: '确认支付',
    mockPayLoading: '处理中…',
    mockPaySuccess: (processing: number, narration: number) =>
      `支付成功！已增加 ${processing} 分钟处理额度` +
      (narration > 0 ? `、${narration} 分钟解说额度` : '') +
      '。',
    mockPayErrorDb: '模拟付费需要数据库环境，请配置 DATABASE_URL 后重试。',
    mockPayErrorGeneric: '支付失败，请稍后重试。',

    freeStartMessage: '欢迎使用免费额度！\n您可以直接开始创建视频（单次最长 3 分钟）。',
  },
  en: {
    backToDashboard: 'Back to Dashboard',

    heroTag: 'Flexible quotas · Transparent pricing',
    heroTitle: 'Choose the plan that fits you',
    heroDesc: 'From light learning to heavy creation, find the plan that matches you best. All plans include 8-language support and high-quality study card generation.',

    monthlyTitle: 'Monthly Subscription Plans',
    monthlyBadge: 'Recommended for long-term',

    monthlyQuotaLabel: 'Monthly processing quota',
    narrationQuotaLabel: 'Monthly narration quota',
    singleLimitLabel: 'Per-video limit',
    dailyLimitLabel: 'Daily processing limit',
    targetLabel: 'Target users',

    subscribePro: 'Subscribe to Pro',
    choosePlan: 'Choose this plan',

    plansFooter: 'All plans include: 8 language support · Auto scene study cards · Base narration quota · Permanent study card retention',

    addonsTitle: 'Add-on Quota Packs',
    addonsSubtitle:
      'Narration packs add equal processing and narration minutes. Buy a video processing pack when you only need processing.',
    buyNow: 'Buy now',

    tipsTitle: 'Good to know',
    tip1: 'Generated video files are automatically cleaned up after your first download. Study cards are retained long-term.',
    tip2:
      'Processing quota is charged by processed video time. Narration quota is also charged when narrated audio is enabled. Narration packs include the same number of processing minutes.',
    tip3: 'This is Beta pricing. Feedback via Contact Support is welcome.',

    // Free plan
    startFree: 'Start for Free',
    freeBadge: 'Default',

    mockPayTitle: 'Confirm mock payment',
    mockPayBeta: 'Beta mock checkout — no real charge.',
    mockPayItem: 'Item',
    mockPayPrice: 'Price',
    mockPayAdds: 'You will receive',
    mockPayProcessing: 'Processing',
    mockPayNarration: 'Narration',
    mockPayMinutes: 'min',
    mockPayPlanNote: 'Your active plan will switch and quota is added immediately.',
    mockPayCancel: 'Cancel',
    mockPayConfirm: 'Confirm payment',
    mockPayLoading: 'Processing…',
    mockPaySuccess: (processing: number, narration: number) =>
      `Payment successful! Added ${processing} min processing` +
      (narration > 0 ? ` and ${narration} min narration` : '') +
      ' quota.',
    mockPayErrorDb: 'Mock checkout requires a database. Configure DATABASE_URL and try again.',
    mockPayErrorGeneric: 'Payment failed. Please try again.',

    freeStartMessage: 'Welcome to the Free tier!\nYou can start creating videos right away (max 3 minutes per video).',
  },
}

type Plan = {
  id: string
  icon: string
  name: string
  price: string
  monthlyQuota: string
  narrationQuota: string
  processingMinutes: number
  narrationMinutes: number
  singleLimit: string
  dailyLimit: string
  target: string
  highlight?: boolean
  badge?: string
}

type Addon = {
  id: string
  name: string
  price: string
  duration: string
  note: string
  processingMinutes: number
  narrationMinutes: number
}

type PendingPurchase = {
  kind: 'plan' | 'addon'
  id: string
  name: string
  price: string
  processingMinutes: number
  narrationMinutes: number
  isPlan: boolean
}

export function PricingPage() {
  const navigate = useNavigate()
  const [lang, setLang] = useState<Lang>('en')
  const [pending, setPending] = useState<PendingPurchase | null>(null)
  const [purchasing, setPurchasing] = useState(false)
  const [purchaseError, setPurchaseError] = useState<string | null>(null)
  const t = content[lang]

  // Bilingual plan data
  const monthlyPlans: Plan[] = [
    {
      id: 'free',
      icon: '🟢',
      name: 'Free',
      price: lang === 'zh' ? '免费' : 'Free',
      monthlyQuota: lang === 'zh' ? '5 分钟' : '5 min',
      narrationQuota: lang === 'zh' ? '5 分钟' : '5 min',
      processingMinutes: 5,
      narrationMinutes: 5,
      singleLimit: '≤ ' + (lang === 'zh' ? '3 分钟' : '3 min'),
      dailyLimit: lang === 'zh' ? '按月额度' : 'By monthly quota',
      target: lang === 'zh' ? '新注册用户（默认）' : 'New registered users (default)',
      badge: t.freeBadge,
    },
    {
      id: 'lite',
      icon: '🔵',
      name: 'Lite',
      price: '¥29 / ' + (lang === 'zh' ? '月' : 'mo'),
      monthlyQuota: lang === 'zh' ? '120 分钟' : '120 min',
      narrationQuota: lang === 'zh' ? '120 分钟' : '120 min',
      processingMinutes: 120,
      narrationMinutes: 120,
      singleLimit: '≤ ' + (lang === 'zh' ? '15 分钟' : '15 min'),
      dailyLimit: '≤ ' + (lang === 'zh' ? '60 分钟' : '60 min'),
      target: lang === 'zh' ? '轻度学习 / 体验用户' : 'Light learners / Trial users',
    },
    {
      id: 'pro',
      icon: '🟣',
      name: 'Pro',
      price: '¥59 / ' + (lang === 'zh' ? '月' : 'mo'),
      monthlyQuota: lang === 'zh' ? '300 分钟' : '300 min',
      narrationQuota: lang === 'zh' ? '300 分钟' : '300 min',
      processingMinutes: 300,
      narrationMinutes: 300,
      singleLimit: '≤ ' + (lang === 'zh' ? '30 分钟' : '30 min'),
      dailyLimit: '≤ ' + (lang === 'zh' ? '120 分钟' : '120 min'),
      target: lang === 'zh' ? '主力学习用户' : 'Mainstream learners',
      highlight: true,
      badge: lang === 'zh' ? '最受欢迎' : 'Most popular',
    },
    {
      id: 'max',
      icon: '🟠',
      name: 'Max',
      price: '¥99 / ' + (lang === 'zh' ? '月' : 'mo'),
      monthlyQuota: lang === 'zh' ? '450 分钟' : '450 min',
      narrationQuota: lang === 'zh' ? '450 分钟' : '450 min',
      processingMinutes: 450,
      narrationMinutes: 450,
      singleLimit: '≤ ' + (lang === 'zh' ? '50 分钟' : '50 min'),
      dailyLimit: '≤ ' + (lang === 'zh' ? '150 分钟' : '150 min'),
      target: lang === 'zh' ? '教师 / 重度用户 / 内容创作者' : 'Teachers / Heavy users / Creators',
    },
  ]

  // Bilingual add-on data
  const addons: Addon[] = [
    {
      id: 'processing-120',
      name: lang === 'zh' ? '视频处理包' : 'Video Processing Pack',
      price: '¥9.9',
      duration: lang === 'zh' ? '120 分钟' : '120 min',
      processingMinutes: 120,
      narrationMinutes: 0,
      note:
        lang === 'zh'
          ? '增加基础处理额度，不增加解说额度'
          : 'Adds processing quota only, not narration quota',
    },
    {
      id: 's',
      name: lang === 'zh' ? '解说包 S' : 'Narration Pack S',
      price: '¥19',
      duration: lang === 'zh' ? '60 分钟' : '60 min',
      processingMinutes: 60,
      narrationMinutes: 60,
      note:
        lang === 'zh'
          ? '含 60 分钟处理 + 60 分钟解说'
          : '60 min processing + 60 min narration',
    },
    {
      id: 'm',
      name: lang === 'zh' ? '解说包 M' : 'Narration Pack M',
      price: '¥39',
      duration: lang === 'zh' ? '150 分钟' : '150 min',
      processingMinutes: 150,
      narrationMinutes: 150,
      note:
        lang === 'zh'
          ? '含 150 分钟处理 + 150 分钟解说，可累积'
          : '150 min processing + 150 min narration, stackable',
    },
    {
      id: 'l',
      name: lang === 'zh' ? '解说包 L' : 'Narration Pack L',
      price: '¥69',
      duration: lang === 'zh' ? '300 分钟' : '300 min',
      processingMinutes: 300,
      narrationMinutes: 300,
      note:
        lang === 'zh'
          ? '含 300 分钟处理 + 300 分钟解说，可累积'
          : '300 min processing + 300 min narration, stackable',
    },
  ]

  const openPurchase = (item: PendingPurchase) => {
    setPurchaseError(null)
    setPending(item)
  }

  const closePurchase = () => {
    if (purchasing) return
    setPending(null)
    setPurchaseError(null)
  }

  const handleSubscribe = (plan: Plan) => {
    if (plan.id === 'free') {
      navigate('/create')
      return
    }
    openPurchase({
      kind: 'plan',
      id: plan.id,
      name: plan.name,
      price: plan.price,
      processingMinutes: plan.processingMinutes,
      narrationMinutes: plan.narrationMinutes,
      isPlan: true,
    })
  }

  const handleBuyAddon = (addon: Addon) => {
    openPurchase({
      kind: 'addon',
      id: addon.id,
      name: addon.name,
      price: addon.price,
      processingMinutes: addon.processingMinutes,
      narrationMinutes: addon.narrationMinutes,
      isPlan: false,
    })
  }

  const handleConfirmPurchase = async () => {
    if (!pending || purchasing) return
    setPurchasing(true)
    setPurchaseError(null)
    try {
      await ensureDevSession()
      const res = await apiFetch('/api/billing/mock-purchase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: pending.kind, id: pending.id }),
      })
      const data = (await res.json()) as MockPurchaseResponse & {
        error?: string
      }
      if (!res.ok) {
        setPurchaseError(
          res.status === 503 ? t.mockPayErrorDb : data.error ?? t.mockPayErrorGeneric,
        )
        return
      }
      setPending(null)
      window.dispatchEvent(new CustomEvent('quota-updated'))
      alert(
        `${t.mockPaySuccess(data.addedProcessingMinutes, data.addedNarrationMinutes)}\n` +
          (lang === 'zh'
            ? `当前可用：处理 ${data.processingRemainingMinutes} 分钟，解说 ${data.narrationRemainingMinutes} 分钟。`
            : `Available now: ${data.processingRemainingMinutes} min processing, ${data.narrationRemainingMinutes} min narration.`),
      )
    } catch {
      setPurchaseError(t.mockPayErrorGeneric)
    } finally {
      setPurchasing(false)
    }
  }

  return (
    <div className="min-h-dvh bg-[#f0fdf4] text-[#4a5568]">
      {/* 顶部 Header */}
      <div className="border-b border-[#d1fae5] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              onClick={() => navigate('/dashboard')}
              className="flex cursor-pointer items-center gap-2"
            >
              <div className="bg-gradient-to-r from-[#86efac] to-[#4ade80] bg-clip-text text-2xl font-extrabold tracking-tighter text-transparent">
                NarraLingo
              </div>
              <span className="rounded bg-[#d1fae5] px-1.5 py-0.5 text-[10px] font-medium text-[#166534]">
                Beta
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Language switcher */}
            <div className="flex items-center gap-1 rounded-full bg-[#f0fdf4] p-0.5 text-sm">
              <button
                type="button"
                onClick={() => setLang('zh')}
                className={`rounded-full px-2.5 py-0.5 transition ${lang === 'zh' ? 'bg-white shadow text-[#166534] font-medium' : 'text-[#718096] hover:text-[#4a5568]'}`}
              >
                中文
              </button>
              <button
                type="button"
                onClick={() => setLang('en')}
                className={`rounded-full px-2.5 py-0.5 transition ${lang === 'en' ? 'bg-white shadow text-[#166534] font-medium' : 'text-[#718096] hover:text-[#4a5568]'}`}
              >
                EN
              </button>
            </div>

            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="rounded-full border border-[#d1fae5] bg-white px-4 py-1.5 text-sm font-medium text-[#166534] transition hover:bg-[#f0fdf4]"
            >
              {t.backToDashboard}
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 pb-16 pt-10">
        {/* 标题区 */}
        <div className="mb-10 text-center">
          <div className="mb-3 text-sm uppercase tracking-[3px] text-[#86efac]">{t.heroTag}</div>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#166534]">{t.heroTitle}</h1>
          <p className="mt-3 text-lg text-[#4b5563]">{t.heroDesc}</p>
        </div>

        {/* 月度订阅套餐 */}
        <div className="mb-16">
          <div className="mb-6 flex items-center gap-3">
            <div className="text-2xl font-semibold tracking-tight text-[#166534]">{t.monthlyTitle}</div>
            <div className="rounded-full bg-[#d1fae5] px-3 py-0.5 text-xs font-medium text-[#166534]">{t.monthlyBadge}</div>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {monthlyPlans.map((plan) => (
              <div
                key={plan.id}
                className={`flex flex-col rounded-3xl border bg-white p-6 shadow-sm transition ${
                  plan.highlight
                    ? 'border-[#4ade80] ring-2 ring-[#86efac]/40'
                    : 'border-[#d1fae5]'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-3xl">{plan.icon}</div>
                    <div className="mt-2 text-xl font-semibold tracking-tight">{plan.name}</div>
                  </div>
                  {plan.badge && (
                    <div className="rounded-full bg-[#166534] px-3 py-0.5 text-[10px] font-semibold text-white">
                      {plan.badge}
                    </div>
                  )}
                </div>

                <div className="mt-4 text-3xl font-extrabold tracking-tighter text-[#166534]">
                  {plan.price}
                </div>

                <div className="mt-6 space-y-3 text-sm">
                  <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                    <span className="text-[#718096]">{t.monthlyQuotaLabel}</span>
                    <span className="font-medium text-[#166534]">{plan.monthlyQuota}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                    <span className="text-[#718096]">{t.narrationQuotaLabel}</span>
                    <span className="font-medium text-[#166534]">{plan.narrationQuota}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                    <span className="text-[#718096]">{t.singleLimitLabel}</span>
                    <span className="font-medium">{plan.singleLimit}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                    <span className="text-[#718096]">{t.dailyLimitLabel}</span>
                    <span className="font-medium">{plan.dailyLimit}</span>
                  </div>
                  <div className="pt-1 text-[#718096]">
                    {t.targetLabel}：<span className="font-medium text-[#4a5568]">{plan.target}</span>
                  </div>
                </div>

                <div className="mt-auto pt-6">
                  <button
                    type="button"
                    onClick={() => handleSubscribe(plan)}
                    className={`w-full rounded-2xl py-3 text-sm font-semibold transition ${
                      plan.id === 'free'
                        ? 'border border-[#4ade80] bg-[#f0fdf4] text-[#166534] hover:bg-white'
                        : plan.highlight
                        ? 'bg-[#166534] text-white hover:bg-[#14532d]'
                        : 'border border-[#86efac] bg-white text-[#166534] hover:bg-[#f0fdf4]'
                    }`}
                  >
                    {plan.id === 'free' ? t.startFree : plan.highlight ? t.subscribePro : t.choosePlan}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-center text-xs text-[#9ca3af]">
            {t.plansFooter}
          </div>
        </div>

        {/* 额外额度包 */}
        <div>
          <div className="mb-6">
            <div className="text-2xl font-semibold tracking-tight text-[#166534]">{t.addonsTitle}</div>
            <div className="mt-1 text-sm text-[#718096]">{t.addonsSubtitle}</div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {addons.map((addon) => (
              <div
                key={addon.id}
                className="flex flex-col rounded-2xl border border-[#d1fae5] bg-white p-5"
              >
                <div className="text-lg font-semibold">{addon.name}</div>
                <div className="mt-1 text-2xl font-extrabold tracking-tight text-[#166534]">
                  {addon.price}
                </div>
                <div className="mt-2 text-sm text-[#4a5568]">{addon.duration}</div>
                <div className="mt-1 text-xs text-[#86efac]">{addon.note}</div>

                <button
                  type="button"
                  onClick={() => handleBuyAddon(addon)}
                  className="mt-5 rounded-xl border border-[#86efac] py-2.5 text-sm font-medium text-[#166534] transition hover:bg-[#f0fdf4]"
                >
                  {t.buyNow}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 底部说明 */}
        <div className="mt-12 rounded-2xl border border-[#d1fae5] bg-white/60 p-6 text-sm text-[#4b5563]">
          <div className="font-medium text-[#166534]">{t.tipsTitle}</div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed">
            <li>{t.tip1}</li>
            <li>{t.tip2}</li>
            <li>{t.tip3}</li>
          </ul>
        </div>
      </div>

      {pending && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="presentation"
          onClick={closePurchase}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mock-pay-title"
            className="w-full max-w-md rounded-3xl border border-[#d1fae5] bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-xs font-medium uppercase tracking-wider text-[#86efac]">
              {t.mockPayBeta}
            </div>
            <h2
              id="mock-pay-title"
              className="mt-2 text-xl font-bold tracking-tight text-[#166534]"
            >
              {t.mockPayTitle}
            </h2>

            <div className="mt-5 space-y-3 text-sm">
              <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                <span className="text-[#718096]">{t.mockPayItem}</span>
                <span className="font-medium text-[#166534]">{pending.name}</span>
              </div>
              <div className="flex justify-between border-b border-[#f0fdf4] pb-2">
                <span className="text-[#718096]">{t.mockPayPrice}</span>
                <span className="font-semibold text-[#166534]">{pending.price}</span>
              </div>
              <div>
                <div className="text-[#718096]">{t.mockPayAdds}</div>
                <div className="mt-1 font-medium text-[#166534]">
                  +{pending.processingMinutes} {t.mockPayMinutes} {t.mockPayProcessing}
                  {pending.narrationMinutes > 0 && (
                    <>
                      {' '}
                      · +{pending.narrationMinutes} {t.mockPayMinutes} {t.mockPayNarration}
                    </>
                  )}
                </div>
              </div>
              {pending.isPlan && (
                <p className="text-xs leading-relaxed text-[#718096]">{t.mockPayPlanNote}</p>
              )}
            </div>

            {purchaseError && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {purchaseError}
              </div>
            )}

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                disabled={purchasing}
                onClick={closePurchase}
                className="flex-1 rounded-2xl border border-[#d1fae5] py-2.5 text-sm font-medium text-[#166534] transition hover:bg-[#f0fdf4] disabled:opacity-50"
              >
                {t.mockPayCancel}
              </button>
              <button
                type="button"
                disabled={purchasing}
                onClick={() => void handleConfirmPurchase()}
                className="flex-1 rounded-2xl bg-[#166534] py-2.5 text-sm font-semibold text-white transition hover:bg-[#14532d] disabled:opacity-50"
              >
                {purchasing ? t.mockPayLoading : t.mockPayConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
