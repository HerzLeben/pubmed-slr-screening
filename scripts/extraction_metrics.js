// Accuracy of the extraction scoring. The same calculation as metrics() in score_extraction.py
// (tests/test_score_extraction.py runs both on one input and compares). build_report.py --run eval-3
// inlines this file into the report, so the screen recounts while the human scores.
//   items: [{review, pmid, name, auto}]   auto = 'correct' | 'wrong' | null (null = the human scores it)
//   human: {review: {"<pmid>\t<name>": true | false}}
// Accuracy = correct / scored; the 95% CI is Wilson's (the paper does not say how it computed its CI).
function extractionMetrics(items, human){
  const Z = 1.959963984540054;
  const wilson = (k, n) => {
    if (!n) return [null, null];
    const p = k / n, d = 1 + Z * Z / n, c = (p + Z * Z / (2 * n)) / d;
    const h = Z * Math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d;
    return [c - h, c + h];
  };
  const blank = () => ({total: 0, scored: 0, correct: 0, pending: 0, rule_correct: 0, rule_wrong: 0, human_correct: 0, human_wrong: 0});
  const out = {overall: blank(), by_review: {}, by_pair: {}};
  for (const it of items){
    const h = (human[it.review] || {})[it.pmid + '\t' + it.name];
    const pair = it.review + '/' + it.pmid;
    if (!out.by_review[it.review]) out.by_review[it.review] = blank();
    if (!out.by_pair[pair]) out.by_pair[pair] = blank();
    for (const m of [out.overall, out.by_review[it.review], out.by_pair[pair]]){
      m.total += 1;
      if (it.auto === 'correct'){ m.scored += 1; m.correct += 1; m.rule_correct += 1; }
      else if (it.auto === 'wrong'){ m.scored += 1; m.rule_wrong += 1; }
      else if (h === true){ m.scored += 1; m.correct += 1; m.human_correct += 1; }
      else if (h === false){ m.scored += 1; m.human_wrong += 1; }
      else m.pending += 1;
    }
  }
  for (const m of [out.overall, ...Object.values(out.by_review), ...Object.values(out.by_pair)]){
    m.accuracy = m.scored ? m.correct / m.scored : null;
    [m.ci_low, m.ci_high] = wilson(m.correct, m.scored);
  }
  return out;
}
if (typeof module !== 'undefined') module.exports = {extractionMetrics};
