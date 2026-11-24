import type { CSSProperties, ReactNode } from 'react'
import { Button, Input, InputNumber } from 'antd'
import type { FlaggedPlayer } from '~/types/admin'
import type { SetEloInputs } from '~/utils/adminFlags'

interface PanelProps {
  player: FlaggedPlayer
  onSubmit: () => void
  loading: boolean
  /** The phone layout: bare inputs stacked, no title or help text. */
  compact: boolean
}

interface TextPanelProps extends PanelProps {
  value: string
  onChange: (value: string) => void
}

const CARD_TONES = {
  neutral: { background: 'var(--bg-card-hover)', border: '1px solid var(--border-card)', title: 'var(--text-primary)' },
  negative: { background: 'var(--negative-soft)', border: '1px solid color-mix(in srgb, var(--negative) 30%, transparent)', title: 'var(--negative)' },
}

function PanelCard({ tone, title, note, noteGap, children }: { tone: keyof typeof CARD_TONES, title: string, note: ReactNode, noteGap: number, children: ReactNode }) {
  const colors = CARD_TONES[tone]
  return (
    <div style={{ padding: '16px 18px', background: colors.background, border: colors.border, borderRadius: 8, margin: '4px 0 8px' }}>
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: colors.title,
        marginBottom: 12,
      }}>
        {title}
      </div>
      {children}
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--text-muted)', marginTop: noteGap }}>{note}</div>
    </div>
  )
}

interface TextFieldProps extends TextPanelProps {
  placeholder: string
  font: string
  action: string
  label: string
  hint: string
}

function TextRepairField({ value, onChange, onSubmit, loading, compact, placeholder, font, action, label, hint }: Omit<TextFieldProps, 'player'>) {
  const input = (style: CSSProperties) => <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
    style={{ ...style, fontFamily: font, fontSize: 13 }} onPressEnter={onSubmit} />
  const button = <Button type="primary" loading={loading} onClick={onSubmit}>{action}</Button>
  if (compact) return <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>{input({ width: '100%' })}{button}</div>
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
        {label}
        <span style={{ color: 'var(--text-muted)', marginLeft: 8, fontStyle: 'italic' }}>{hint}</span>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{input({ maxWidth: 280 })}{button}</div>
    </div>
  )
}

export function FixStatsPanel({ player, ...field }: TextPanelProps) {
  const body = <TextRepairField {...field} placeholder={player.autoSlug} font="var(--font-mono)" action="Fetch Stats"
    label="TennisAbstract Slug" hint={`(auto: ${player.autoSlug}${player.taSlug ? ` · saved: ${player.taSlug}` : ''})`} />
  if (field.compact) return body
  return <PanelCard tone="neutral" title={`Fix Rolling Stats — ${player.playerName}`} noteGap={6}
    note="The slug is saved to the DB and used for future ingests. Leave unchanged to use the auto-generated slug.">{body}</PanelCard>
}

export function FetchEloPanel({ player, ...field }: TextPanelProps) {
  const body = <TextRepairField {...field} placeholder={player.playerName} font="var(--font-body)" action="Fetch ELO"
    label="TennisAbstract Name" hint="(edit if spelling differs from our DB)" />
  if (field.compact) return body
  // No Challenger ELO page exists: the backend searches both tables, since that label covers men's Challengers and WTA 125.
  const eloTables = player.tour?.toUpperCase() === 'CHALLENGER' ? 'ATP/WTA' : player.tour
  return <PanelCard tone="negative" title={`Fetch ELO from TennisAbstract — ${player.playerName}`} noteGap={6}
    note={`Searches TennisAbstract's ${eloTables} ELO ratings table for this name. If found, Hard/Clay/Grass ELO are also saved.`}>{body}</PanelCard>
}

interface SetEloPanelProps extends PanelProps {
  inputs: SetEloInputs
  onChange: (key: keyof SetEloInputs, value: string) => void
}

const ELO_FIELDS = [
  { key: 'elo', short: 'Overall*', label: 'Overall ELO', required: true },
  { key: 'hard', short: 'Hard', label: 'Hard ELO', required: false },
  { key: 'clay', short: 'Clay', label: 'Clay ELO', required: false },
  { key: 'grass', short: 'Grass', label: 'Grass ELO', required: false },
] as const

export function SetEloPanel({ player, inputs, onChange, onSubmit, loading, compact }: SetEloPanelProps) {
  const field = (key: keyof SetEloInputs, width: CSSProperties['width']) => <InputNumber
    value={inputs[key] ? Number(inputs[key]) : undefined}
    onChange={(v) => onChange(key, String(v ?? ''))}
    placeholder={key === 'elo' ? '1500' : 'optional'}
    min={500}
    max={3000}
    step={10}
    style={{ width }}
  />
  const save = (style?: CSSProperties) => <Button type="primary" loading={loading} disabled={!inputs.elo} onClick={onSubmit} style={style}>Save ELO</Button>

  if (compact) return (
    <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
      {ELO_FIELDS.map(({ key, short }) => (
        <div key={key}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{short}</div>
          {field(key, '100%')}
        </div>
      ))}
      {save({ gridColumn: '1 / -1' })}
    </div>
  )
  return (
    <PanelCard tone="negative" title={`Set ELO Manually — ${player.playerName}`} noteGap={10}
      note="Typical ATP/WTA range: 1300–2100. Qualifiers are often 1300–1500.">
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        {ELO_FIELDS.map(({ key, label, required }) => (
          <div key={key}>
            <div style={{
              fontFamily: 'var(--font-body)',
              fontSize: 12,
              color: required ? 'var(--text-secondary)' : 'var(--text-muted)',
              marginBottom: 4,
            }}>
              {label}{required && <span style={{ color: 'var(--negative)', marginLeft: 2 }}>*</span>}
            </div>
            {field(key, 120)}
          </div>
        ))}
        {save()}
      </div>
    </PanelCard>
  )
}
