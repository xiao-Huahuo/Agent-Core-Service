/*
 * Git push file-tree construction.
 *
 * Usage:
 * Converts the flat `git diff --name-status` response into directory-first
 * nodes consumed by GitPushFileTree.
 */

/** Minimal backend file entry needed to build a push preview tree. */
export interface GitPushFileEntry {
  /** Knowledge-root-relative file path. */
  path: string
  /** Git name-status code shown beside the leaf node. */
  status: string
}

/** One directory or file in the push preview tree. */
export interface GitPushTreeNode {
  /** Segment name displayed in the row. */
  name: string
  /** Full knowledge-root-relative path represented by this node. */
  path: string
  /** Git status for files; directories use an empty string. */
  status: string
  /** Whether this node represents a directory. */
  directory: boolean
  /** Nested directory and file nodes. */
  children: GitPushTreeNode[]
}

/** Sort directories before files, then compare names without case sensitivity. */
function sortTree(nodes: GitPushTreeNode[]): void {
  nodes.sort((left, right) => {
    if (left.directory !== right.directory) return left.directory ? -1 : 1
    return left.name.localeCompare(right.name, undefined, { sensitivity: 'base' })
  })
  for (const node of nodes) sortTree(node.children)
}

/** Build a stable relative-directory tree from flat unpushed file entries. */
export function buildGitPushTree(files: GitPushFileEntry[]): GitPushTreeNode[] {
  const roots: GitPushTreeNode[] = []

  for (const file of files) {
    const segments = file.path.replace(/\\/g, '/').split('/').filter(Boolean)
    let level = roots
    let accumulatedPath = ''

    segments.forEach((segment, index) => {
      accumulatedPath = accumulatedPath ? `${accumulatedPath}/${segment}` : segment
      const directory = index < segments.length - 1
      let node = level.find((candidate) => candidate.name === segment && candidate.directory === directory)
      if (!node) {
        node = {
          name: segment,
          path: accumulatedPath,
          status: directory ? '' : file.status,
          directory,
          children: [],
        }
        level.push(node)
      }
      level = node.children
    })
  }

  sortTree(roots)
  return roots
}
