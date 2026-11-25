import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SignOutButton from "./sign-out";
import { Activity, ArrowUpRight, BarChart3, Bitcoin, CandlestickChart, CircleDollarSign, Globe2, ShieldCheck, Wallet } from "lucide-react";

const markets = [
  { name: "台灣市場", ticker: "TW MARKET", detail: "上市・上櫃・ETF", icon: CandlestickChart, state: "資料源待設定" },
  { name: "美國市場", ticker: "US MARKET", detail: "NYSE・NASDAQ・ETF", icon: Globe2, state: "資料源待設定" },
  { name: "加密貨幣", ticker: "CRYPTO", detail: "BTC・ETH・主流資產", icon: Bitcoin, state: "可接公開行情 API" },
  { name: "期貨市場", ticker: "FUTURES", detail: "台指期・美股指數期貨", icon: BarChart3, state: "第二階段接入" }
];

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <main className="dashboardShell">
    <header className="topbar">
      <div className="brandInline"><div className="brandMark small"><Activity size={19}/></div><div><strong>GLOBAL RADAR</strong><small>PRIVATE MARKET TERMINAL</small></div></div>
      <div className="userTools"><span className="userEmail">{user.email}</span><SignOutButton/></div>
    </header>
    <section className="welcome">
      <div><p className="eyebrow">PERSONAL FINANCIAL COMMAND CENTER</p><h1>市場總覽<span className="liveDot"/> </h1><p className="muted">你的全球金融研究工作區已建立。行情連線與個人資料模組將分階段啟用。</p></div>
      <div className="privateBadge"><ShieldCheck size={16}/> 私人模式</div>
    </section>

    <section className="marketGrid">
      {markets.map((m) => { const Icon=m.icon; return <article className="marketCard" key={m.ticker}><div className="cardTop"><span className="iconTile"><Icon size={20}/></span><span className="statusPill">{m.state}</span></div><p className="cardEyebrow">{m.ticker}</p><h2>{m.name}</h2><p className="muted">{m.detail}</p><div className="cardFoot"><span>行情模組</span><ArrowUpRight size={16}/></div></article>; })}
    </section>

    <section className="sectionHeading"><div><p className="eyebrow">WORKSPACE MODULES</p><h2>研究工具</h2></div><span className="muted">第一階段・核心介面</span></section>
    <section className="toolGrid">
      <article className="toolCard"><CandlestickChart/><div><h3>專業圖表工作區</h3><p>規劃多週期 K 線、技術指標、趨勢線與自選商品。</p></div><span className="coming">下一階段</span></article>
      <article className="toolCard"><Activity/><div><h3>智慧選股雷達</h3><p>保留既有台股爆發雷達，逐步整合全球篩選器。</p></div><span className="coming">整合中</span></article>
      <article className="toolCard"><Wallet/><div><h3>投資組合</h3><p>管理成本、持倉、損益、配息與資產配置。</p></div><span className="coming">規劃中</span></article>
      <article className="toolCard"><CircleDollarSign/><div><h3>模擬交易</h3><p>虛擬資金、模擬成交、交易紀錄與績效統計。</p></div><span className="coming">規劃中</span></article>
    </section>

    <section className="noticePanel"><ShieldCheck size={20}/><div><strong>資料與交易安全</strong><p>目前是第一階段私人登入骨架，尚未連接即時行情或真實券商。所有交易功能規劃為模擬交易，不會送出真實委託。</p></div></section>
    <footer className="dashboardFooter">GLOBAL RADAR · PRIVATE BUILD · PHASE 1 <span>登入帳號：{user.email}</span></footer>
  </main>;
}