import { useEffect, useState } from 'react'

const MOBILE_BREAKPOINT = 768

export function useIsMobile(breakpoint = MOBILE_BREAKPOINT): boolean {
  const getValue = () =>
    typeof window !== 'undefined' ? window.innerWidth <= breakpoint : false

  const [isMobile, setIsMobile] = useState<boolean>(getValue)

  useEffect(() => {
    const onResize = () => setIsMobile(getValue())
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])

  return isMobile
}

