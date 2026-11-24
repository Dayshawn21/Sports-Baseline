import PageHead from '~/components/shared/PageHead'
import OddsConverterCard from '~/components/tools/OddsConverterCard'
import NoVigCard from '~/components/tools/NoVigCard'
import EvCard from '~/components/tools/EvCard'
import KellyCard from '~/components/tools/KellyCard'
import EntryCard from '~/components/tools/EntryCard'
import './tools.css'

export default function ToolsPage() {
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="Tools" meta="Runs in your browser. Nothing is saved or sent." />
    <div className="tools-grid">
      <OddsConverterCard />
      <NoVigCard />
      <EvCard />
      <KellyCard />
      <EntryCard />
    </div>
  </div></div>
}
