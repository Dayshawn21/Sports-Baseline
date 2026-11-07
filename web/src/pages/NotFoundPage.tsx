import { Link, useLocation } from 'react-router-dom'
import PageHead from '~/components/shared/PageHead'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'

export default function NotFoundPage() {
  const { pathname } = useLocation()
  useRegisterDetailTitle('Page not found')
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="Page not found" meta={<>Nothing lives at <code>{pathname}</code>. <Link to="/">Back to home</Link></>} />
  </div></div>
}
