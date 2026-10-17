import { useState } from 'react'
import { Select } from 'antd'
import ModelCalibrationChart from '~/components/tennis/model/ModelCalibrationChart'
import ModelClv from '~/components/tennis/model/ModelClv'
import ModelComponentTable from '~/components/tennis/model/ModelComponentTable'
import ModelPrizePicksTable from '~/components/tennis/model/ModelPrizePicksTable'
import ModelSection from '~/components/shared/ModelSection'
import PageHead from '~/components/shared/PageHead'
import ModelTierCards from '~/components/tennis/model/ModelTierCards'
import ModelVerdictCards from '~/components/tennis/model/ModelVerdictCards'
import { useModelPredictions, useModelPrizePicksLines, useModelPropTiers } from '~/hooks/useModelTrackRecord'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'
import { unsettledVersionNote, versionOptions } from '~/utils/trackRecord'
import './tennis-model.css'

export default function TennisModelPage() {
  const [modelVersion, setModelVersion] = useState<string>()
  const predictions = useModelPredictions(modelVersion)
  const lines = useModelPrizePicksLines()
  const tiers = useModelPropTiers()
  const gradedAt = predictions.data?.gradedAt
  const versionNote = predictions.data ? unsettledVersionNote(predictions.data) : null

  return (
    <div className="page-shell tennis-model"><div className="page-container is-wide">
      <PageHead
        title="Track record"
        meta={<>Settled matches{gradedAt && <> · last graded {fmtDateCT(gradedAt)} {fmtTimeCT(gradedAt)}</>}</>}
      />

      {predictions.data && (
        <div className="tennis-model-version">
          <span className="tennis-model-version__label">Model version</span>
          <Select aria-label="Model version" value={predictions.data.modelVersion} onChange={setModelVersion}
            options={versionOptions(predictions.data.versions)} popupMatchSelectWidth={false} />
          {versionNote && <p className="tennis-model-version__note">{versionNote}</p>}
        </div>
      )}

      <ModelVerdictCards modelVersion={modelVersion} />

      <h2 className="tennis-model-heading">Match winner · components against the market</h2>
      <div className="tennis-model-grid">
        <ModelSection query={predictions} loading="Grading predictions...">
          {(data) => <>
            <ModelComponentTable data={data} />
            <ModelCalibrationChart series={data.calibration} />
          </>}
        </ModelSection>
      </div>

      <h2 className="tennis-model-heading">Closing-line value · did the price move toward the model?</h2>
      <ModelSection query={predictions} loading="Grading predictions...">
        {(data) => <ModelClv data={data} />}
      </ModelSection>
      <h2 className="tennis-model-heading">PrizePicks lines · how blind overs settle</h2>
      <ModelSection query={lines} loading="Settling PrizePicks lines...">
        {(data) => <ModelPrizePicksTable data={data} />}
      </ModelSection>
      <h2 className="tennis-model-heading">Model picks by confidence tier · frozen snapshots</h2>
      <ModelSection query={tiers} loading="Grading confidence tiers...">
        {(data) => <ModelTierCards data={data} />}
      </ModelSection>
    </div></div>
  )
}
