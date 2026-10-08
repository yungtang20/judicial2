// question_queue.js
// Question Queue：UNKNOWN → CoreIssue → Question → 狀態機（PENDING/ASKED/ANSWERED/OBSOLETE/NEED_REVIEW）。
// State Engine 邊界：僅管理問句佇列與狀態轉換；不產生問句文本、不執行 LLM。

function createQuestion({ questionId, coreIssueId, elementIds, candidateIds, priority, status = 'PENDING', text }) {
  return { questionId, coreIssueId, elementIds, candidateIds, priority, status, text };
}

function transition(queueItem, newStatus) {
  const valid = ['PENDING', 'ASKED', 'ANSWERED', 'OBSOLETE', 'NEED_REVIEW'];
  if (!valid.includes(newStatus)) {
    throw new Error(`Invalid status: ${newStatus}`);
  }
  return { ...queueItem, status: newStatus };
}

function markObsolete(queueItem) {
  return transition(queueItem, 'OBSOLETE');
}

function hasRedundant(existingQueue, newQuestion) {
  return existingQueue.some(q =>
    q.coreIssueId === newQuestion.coreIssueId &&
    q.status !== 'OBSOLETE' &&
    q.elementIds.join(',') === newQuestion.elementIds.join(',')
  );
}

module.exports = { createQuestion, transition, markObsolete, hasRedundant };
