import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const languages = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'vi', name: 'Tiếng Việt', flag: '🇻🇳' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
];

type Lang = 'zh' | 'en';

const content = {
  zh: {
    brand: '影语通Pro',
    title1: '把任何视频，',
    title2: '变成你的语言学习老师',
    desc: '上传本地视频或链接，生成解说声道视频 + 语言学习素材。',
    ctaPrimary: '立即开始使用',
    ctaSecondary: '了解详情',
    langSupportTitle: '我们支持这些语言',
    beta: 'Beta',
    benefit1: '✓ 支持 8 种语言',
    benefit2: '✓ 语言与难度自由选择',
    benefit3: '✓ 自动生成学习卡片',
    benefit4: '✓ 保留原片画质与字幕',
  },
  en: {
    brand: 'NarraLingo',
    title1: 'Turn Any Video',
    title2: 'Into Your Language Learning Teacher',
    desc: 'Upload local videos or links to generate narrated videos with audio tracks + language learning materials.',
    ctaPrimary: 'Get Started',
    ctaSecondary: 'Learn More',
    langSupportTitle: 'Languages We Support',
    beta: 'Beta',
    benefit1: '✓ Supports 8 languages',
    benefit2: '✓ Flexible language & difficulty selection',
    benefit3: '✓ Auto-generates study cards',
    benefit4: '✓ Preserves original video quality & subtitles',
  },
};

export function StartPage() {
  const navigate = useNavigate();
  const [lang, setLang] = useState<Lang>('en');
  const t = content[lang];

  const scrollToDemo = () => {
    const demoSection = document.getElementById('demo');
    if (demoSection) {
      demoSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="min-h-dvh bg-[#f0fdf4] text-[#4a5568]">
      {/* 简洁导航 */}
      <nav className="flex items-center justify-between px-8 py-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="text-2xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-[#86efac] to-[#4ade80]">
            {t.brand}
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-white/70 text-[#718096] font-medium">{t.beta}</span>
        </div>

        {/* 语言切换器 */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => setLang('zh')}
            className={`px-3 py-1 rounded-full transition ${lang === 'zh' ? 'bg-white shadow text-[#4a5568] font-medium' : 'text-[#718096] hover:text-[#4a5568]'}`}
          >
            中文
          </button>
          <button
            onClick={() => setLang('en')}
            className={`px-3 py-1 rounded-full transition ${lang === 'en' ? 'bg-white shadow text-[#4a5568] font-medium' : 'text-[#718096] hover:text-[#4a5568]'}`}
          >
            EN
          </button>
        </div>

      </nav>

      {/* Hero Section - 清晰价值主张版 */}
      <section className="max-w-5xl mx-auto px-8 pt-16 pb-20">
        <div className="max-w-3xl">
          <h1 className="text-[52px] md:text-[68px] leading-[1.08] font-extrabold tracking-[-0.04em] mb-6">
            {t.title1}<br />
            <span className="text-[#718096]">{t.title2}</span>
          </h1>

          <p className="text-xl text-[#718096] max-w-xl mb-8 leading-relaxed">
            {t.desc}
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="inline-flex items-center justify-center gap-3 bg-gradient-to-r from-[#86efac] to-[#4ade80] text-white px-10 py-5 rounded-2xl font-bold text-lg shadow-lg hover:shadow-xl active:scale-[0.985] transition-all"
            >
              {t.ctaPrimary}
              <span aria-hidden="true">→</span>
            </button>

            <button 
              onClick={scrollToDemo}
              className="px-8 py-5 rounded-2xl font-semibold text-base border border-white/70 bg-white/60 hover:bg-white transition-colors cursor-pointer"
            >
              {t.ctaSecondary}
            </button>
          </div>

        </div>
      </section>

      {/* 支持的语言 - 更紧凑优雅版（不再每个语言单独大框） */}
      <section className="border-t border-white/60 bg-white/40 py-14">
        <div className="max-w-5xl mx-auto px-8">
          <div className="mb-6">
            <div className="text-3xl font-semibold tracking-tight">{t.langSupportTitle}</div>
          </div>

          {/* 纯横向流动排列，不用胶囊/pill 包裹 */}
          <div className="bg-[#f0fdf4]/80 rounded-3xl p-8 shadow-sm">
            <div className="flex flex-wrap items-center gap-x-7 gap-y-4">
              {languages.map((lang) => (
                <div 
                  key={lang.code} 
                  className="flex items-center gap-2 group"
                >
                  <span className="text-3xl leading-none select-none opacity-50 group-hover:scale-110 transition-transform">
                    {lang.flag}
                  </span>
                  <span className="font-medium text-[15px] tracking-[-0.01em] whitespace-nowrap">
                    {lang.name}
                    <span className="ml-1 text-xs font-mono tracking-widest text-[#718096] align-middle">
                      {lang.code.toUpperCase()}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 核心卖点 - 移到国旗区域下方 */}
          <div className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm text-[#718096]">
            <div>{t.benefit1}</div>
            <div>{t.benefit2}</div>
            <div>{t.benefit3}</div>
            <div>{t.benefit4}</div>
          </div>

        </div>
      </section>

      {/* Demo 真实示例 */}
      <section id="demo" className="border-t border-white/60 bg-white/30 py-16">
        <div className="max-w-5xl mx-auto px-8">
          <div className="mb-8 text-center">
            <div className="text-3xl font-semibold tracking-tight mb-2">
              {lang === 'zh' ? 'Demo' : 'Demo'}
            </div>
          </div>

          {/* 视频 */}
          <div className="mb-8">
            <div className="text-sm font-medium text-[#718096] mb-3 flex items-center gap-2">
              <span className="inline-block w-2 h-2 bg-[#4ade80] rounded-full"></span>
              {lang === 'zh' ? '生成的解说声道视频' : 'Generated Narration Audio Track'}
            </div>
            <video 
              controls 
              className="mx-auto w-full max-w-[75%] rounded-2xl shadow-lg border border-white/70"
              style={{ maxHeight: '520px', background: '#000' }}
              src="/demo/narrated.mp4"
            >
              您的浏览器不支持 video 标签。
            </video>
          </div>

          {/* 学习卡片 */}
          <div>
            <div className="text-sm font-medium text-[#718096] mb-3 flex items-center gap-2">
              <span className="inline-block w-2 h-2 bg-[#4ade80] rounded-full"></span>
              {lang === 'zh' ? '配套场景学习卡片' : 'Accompanying Study Cards'}
            </div>
            <iframe
              src="/demo/study_cards.html"
              className="w-full rounded-2xl border border-white/70 shadow-lg bg-white"
              style={{ height: '720px' }}
              title="Study Cards"
            />
          </div>
        </div>
      </section>

      {/* 底部轻量 CTA */}
      <div className="py-10 text-center">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-[#4ea8de] hover:text-[#ff8fa3] font-semibold text-lg transition-colors underline underline-offset-4"
        >
          立即进入 NarraLingo →
        </button>
      </div>
    </div>
  );
}
