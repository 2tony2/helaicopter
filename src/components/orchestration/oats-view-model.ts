import type {
  OrchestrationOperationHistoryEntry,
  OrchestrationTaskRecord,
  OvernightOatsRunRecord,
} from "@/lib/types";

const ROOT_PARENT = "__root__";

export interface OatsTaskPrSummary {
  total: number;
  merged: number;
  awaitingChecks: number;
  awaitingReview: number;
  mergeReady: number;
  blocked: number;
  open: number;
}

export interface OatsPrStackItem {
  taskId: string;
  title: string;
  depth: number;
  dependsOn: string[];
  parentTaskId?: string;
  parentBranch?: string | null;
  headBranch?: string | null;
  baseBranch?: string | null;
  status: OrchestrationTaskRecord["status"];
  prState?: string;
  mergeGateStatus?: string;
  reviewBlockingState?: string;
  isStale: boolean;
  isSelected: boolean;
}

export interface OatsViewModel {
  selectedTaskId: string | null;
  selectedNodeId: string | null;
  selectedTask: OrchestrationTaskRecord | null;
  selectedOperationHistory: OrchestrationOperationHistoryEntry[];
  stackItems: OatsPrStackItem[];
  taskPrSummary: OatsTaskPrSummary;
}

type OrderedTaskEntry = {
  task: OrchestrationTaskRecord;
  parentTaskId: string | undefined;
  depth: number;
};

function resolveSelectedTaskId(
  run: OvernightOatsRunRecord,
  selectedTaskId?: string | null
): string | null {
  const taskIds = new Set(run.tasks.map((task) => task.taskId));
  if (selectedTaskId && taskIds.has(selectedTaskId)) {
    return selectedTaskId;
  }
  if (run.activeTaskId && taskIds.has(run.activeTaskId)) {
    return run.activeTaskId;
  }
  return run.tasks[0]?.taskId ?? null;
}

function countTaskPrs(run: OvernightOatsRunRecord): OatsTaskPrSummary {
  const prs = run.tasks
    .map((task) => task.taskPr)
    .filter((taskPr): taskPr is NonNullable<typeof taskPr> => Boolean(taskPr));

  return {
    total: prs.length,
    merged: prs.filter((taskPr) => taskPr.mergeGateStatus === "merged").length,
    awaitingChecks: prs.filter((taskPr) => taskPr.mergeGateStatus === "awaiting_checks").length,
    awaitingReview: prs.filter(
      (taskPr) => taskPr.mergeGateStatus === "awaiting_review_clearance"
    ).length,
    mergeReady: prs.filter((taskPr) => taskPr.mergeGateStatus === "merge_ready").length,
    blocked: prs.filter((taskPr) => taskPr.state === "blocked").length,
    open: prs.filter((taskPr) => taskPr.state === "open").length,
  };
}

function orderedTasks(run: OvernightOatsRunRecord) {
  const tasksById = new Map(run.tasks.map((task) => [task.taskId, task]));
  const branchToTaskId = new Map<string, string>();
  for (const task of run.tasks) {
    const headBranch = task.taskPr?.headBranch;
    if (headBranch) {
      branchToTaskId.set(headBranch, task.taskId);
    }
  }

  const parentTaskIdByTaskId = new Map<string, string | undefined>();
  for (const task of run.tasks) {
    parentTaskIdByTaskId.set(
      task.taskId,
      task.parentBranch ? branchToTaskId.get(task.parentBranch) : undefined
    );
  }

  const childrenByParent = new Map<string, string[]>();
  for (const task of run.tasks) {
    const parentTaskId = parentTaskIdByTaskId.get(task.taskId);
    const parentKey = parentTaskId ?? ROOT_PARENT;
    const siblings = childrenByParent.get(parentKey) ?? [];
    siblings.push(task.taskId);
    childrenByParent.set(parentKey, siblings);
  }

  const orderedTaskIds: string[] = [];
  const seen = new Set<string>();

  function visit(taskId: string) {
    if (seen.has(taskId)) {
      return;
    }
    seen.add(taskId);
    orderedTaskIds.push(taskId);
    for (const childTaskId of childrenByParent.get(taskId) ?? []) {
      visit(childTaskId);
    }
  }

  for (const taskId of childrenByParent.get(ROOT_PARENT) ?? []) {
    visit(taskId);
  }
  for (const task of run.tasks) {
    visit(task.taskId);
  }

  const depthByTaskId = new Map<string, number>();

  function depthFor(taskId: string, trail = new Set<string>()): number {
    if (depthByTaskId.has(taskId)) {
      return depthByTaskId.get(taskId) ?? 0;
    }
    if (trail.has(taskId)) {
      return 0;
    }
    trail.add(taskId);
    const parentTaskId = parentTaskIdByTaskId.get(taskId);
    const depth = parentTaskId ? depthFor(parentTaskId, trail) + 1 : 0;
    depthByTaskId.set(taskId, depth);
    trail.delete(taskId);
    return depth;
  }

  return orderedTaskIds
    .map((taskId) => {
      const task = tasksById.get(taskId);
      if (!task) {
        return null;
      }
      return {
        task,
        parentTaskId: parentTaskIdByTaskId.get(taskId),
        depth: depthFor(taskId),
      };
    })
    .filter((entry): entry is OrderedTaskEntry => entry !== null);
}

export function buildOatsViewModel(
  run: OvernightOatsRunRecord,
  selectedTaskId?: string | null
): OatsViewModel {
  const resolvedSelectedTaskId = resolveSelectedTaskId(run, selectedTaskId);
  const selectedTask =
    run.tasks.find((task) => task.taskId === resolvedSelectedTaskId) ?? null;

  return {
    selectedTaskId: resolvedSelectedTaskId,
    selectedNodeId: selectedTask?.taskId ?? null,
    selectedTask,
    selectedOperationHistory:
      selectedTask?.operationHistory.length
        ? selectedTask.operationHistory
        : run.operationHistory,
    stackItems: orderedTasks(run).map(({ task, parentTaskId, depth }) => ({
      taskId: task.taskId,
      title: task.title,
      depth,
      dependsOn: task.dependsOn,
      parentTaskId,
      parentBranch: task.parentBranch,
      headBranch: task.taskPr?.headBranch,
      baseBranch: task.taskPr?.baseBranch,
      status: task.status,
      prState: task.taskPr?.state,
      mergeGateStatus: task.taskPr?.mergeGateStatus,
      reviewBlockingState: task.taskPr?.reviewSummary?.blockingState,
      isStale: task.taskPr?.isStale ?? false,
      isSelected: task.taskId === resolvedSelectedTaskId,
    })),
    taskPrSummary: countTaskPrs(run),
  };
}
