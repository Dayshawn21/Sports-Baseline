export type SlateCommandTargetKind = 'match' | 'game' | 'team' | 'player'

export interface SlateCommandTargetInput {
  key: string
  kind: SlateCommandTargetKind
  label: string
  context: string
  path: string
  searchTerms?: readonly string[]
}

export interface SlateCommandRowInput {
  key: string
  path: string
  searchTerms: readonly string[]
  targets: readonly SlateCommandTargetInput[]
}

export interface SlateCommandTarget extends Omit<SlateCommandTargetInput, 'searchTerms'> {
  parentPath: string
  searchText: string
}

export interface SlateCommandRow {
  key: string
  path: string
  searchText: string
  targets: SlateCommandTarget[]
}

export interface SlateCommandScope {
  periodKey: string
  rows: readonly SlateCommandRow[]
}
