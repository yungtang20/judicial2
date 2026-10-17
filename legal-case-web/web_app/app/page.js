'use client';

import { useEffect, useState } from 'react';
import { buildMemo } from '../lib/memoTemplates';

export default function Home() {
  const [step, setStep] = useState(0);
  const [caseSummary, setCaseSummary] = useState('');
  const [facts, setFacts] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [memo, setMemo] = useState('');
  const [docMode, setDocMode] = useState('victim');
  const [caseNo, setCaseNo] = useState('');
  const [victimCode, setVictimCode] = useState('');
  const [fraudNo, setFraudNo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('JUD2_SIMPLE_V1');
    if (saved) {
      try {
        const p = JSON.parse(saved);
        setCaseSummary(p.caseSummary || '');
        setStep(p.step || 0);
        setFacts(p.facts || null);
        setQuestions(p.questions || []);
        setAnswers(p.answers || {});
        setMemo(p.memo || '');
        setDocMode(p.docMode || 'victim');
      } catch {}
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('JUD2_SIMPLE_V1', JSON.stringify({
      caseSummary, step, facts, questions, answers, memo, docMode
    }));
  }, [caseSummary, step, facts, questions, answers, memo, docMode]);

  async function callApi(gate, extra = {}) {
    const res = await fetch('/api/llm-proxy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gate, caseSummary, ...extra }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'API 失敗');
    return json.data;
  }

  async function analyze() {
    if (!caseSummary.trim()) {
      alert('請先輸入案情摘要');
      return;
    }
    setLoading(true); setError('');
    try {
      const f = await callApi(1);
      setFacts(f?.facts || []);
      const q = await callApi(2);
      setQuestions(q?.generated_questions || []);
      if (q?.generated_questions?.length) {
        setAnswers(Array(q.generated_questions.length).fill(''));
        setStep(1);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function setAnswer(i, val) {
    setAnswers((prev) => ({ ...prev, [i]: val }));
  }

  function consolidate() {
    const memoText = buildMemo(docMode, caseSummary, { caseNo, victimCode, fraudNo });
    const qaText = questions.map((q, i) => `${i + 1}. ${q}\n答: ${answers[i] || '（未填）'}`).join('\n');
    setMemo(memoText + '\n\n\n【問答整理】\n' + qaText);
    setStep(2);
  }

  function downloadText(content, name) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadDocx() {
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/generate-doc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          templateType: docMode,
          caseSummary,
          caseNumber: { caseNo: '', victimCode: '', fraudNo: '' },
          supplemental: questions.map((q, i) => ({ q, a: answers[i] || '' }))
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || '生成筆錄失敗');
      if (!json.base64) throw new Error('伺服器未回傳 base64');
      const raw = atob(json.base64);
      const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `JUDICIAL2_${docMode}_statement.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-900 text-white p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        <header>
          <h1 className="text-2xl font-bold">JUDICIAL2 筆錄生成器</h1>
        </header>

        {step === 0 && (
          <section className="rounded bg-slate-800 p-4 space-y-3">
            <p className="text-slate-300 text-sm">輸入案情摘要（含時間/地點/人物/動作）。字數不限。</p>
            <textarea
              className="w-full h-40 p-3 rounded bg-slate-700 text-white placeholder:text-slate-400"
              placeholder="例如：甲在咖啡廳趁乙上廁所時，拿未鎖屏手機做 3000 元小額付費儲值..."
              value={caseSummary}
              onChange={(e) => setCaseSummary(e.target.value)}
            />
            <button onClick={analyze} disabled={loading || !caseSummary.trim()}
              className="px-4 py-2 bg-blue-600 rounded text-white disabled:opacity-40">
              {loading ? '分析中...' : '開始分析 (自動 Gate1 + Gate2)'}
            </button>
          </section>
        )}

        {error && <div className="rounded bg-red-900 p-3 text-white">{error}</div>}

        {step === 1 && (
          <div className="space-y-3">
            {facts?.length ? (
              <section className="rounded bg-slate-800 p-4">
                <h2 className="font-semibold mb-2">Gate 1 - 事實登錄</h2>
                <div className="space-y-2">
                  {facts.map((f, i) => (
                    <div key={i} className="p-2 rounded bg-slate-700 text-sm flex gap-2 items-center">
                      <span className="px-2 py-1 bg-slate-600 rounded text-xs">{f.fact_type}</span>
                      <span className="text-xs">{f.epistemic_status}</span>
                      <span>{f.content}</span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {questions.length > 0 && (
              <section className="rounded bg-slate-800 p-4 space-y-2">
                <h2 className="font-semibold mb-1">Gate 2 - 一問一答</h2>
                {questions.map((q, i) => (
                  <div key={i} className="p-2 rounded bg-slate-700">
                    <div className="mb-1 font-medium">Q{i + 1}: {q}</div>
                    <textarea className="w-full h-20 p-2 rounded bg-slate-600 text-white"
                      value={answers[i] || ''} onChange={(e) => setAnswer(i, e.target.value)}
                      placeholder="填寫本題回答" />
                  </div>
                ))}
                <button onClick={consolidate}
                  className="px-4 py-2 bg-emerald-600 rounded text-white">
                  下一步：整合 Memo / Gate 3
                </button>
              </section>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <section className="rounded bg-slate-800 p-4">
              <h2 className="font-semibold mb-2">條陳 / 筆錄 scaffold（Gate 3 自動）</h2>
              <pre className="text-sm whitespace-pre-wrap">{memo}</pre>
              <div className="flex flex-wrap gap-2 mt-3">
                <select value={docMode} onChange={(e) => setDocMode(e.target.value)}
                  className="px-2 py-1 rounded bg-slate-700 text-white">
                  <option value="victim">通用被害人筆錄</option>
                  <option value="suspect">通用涉嫌人筆錄</option>
                  <option value="suspect-transfer">通用涉嫌人筆錄（移送）</option>
                </select>
                <button onClick={downloadDocx} disabled={loading}
                  className="px-4 py-2 bg-amber-600 rounded text-white disabled:opacity-40">
                  下載完整筆錄 (.docx)
                </button>
                <button onClick={() => downloadText(buildFullStatement(), 'JUDICIAL2_statement.txt')}
                  className="px-4 py-2 bg-indigo-600 rounded text-white disabled:opacity-40">
                  下載 .txt scaffold
                </button>
              </div>
            </section>
            <button onClick={() => setStep(0)} className="px-4 py-2 bg-slate-700 rounded text-white">
              重新開始
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
