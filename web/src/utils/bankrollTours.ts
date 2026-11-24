const MAIN_TOURS = ['ATP', 'WTA']

interface Toured {
  tour: string
}

export interface TourSplit<S, P> {
  mainSingles: S[]
  challSingles: S[]
  mainParlays: P[]
  challParlays: P[]
}

function isMainTour(item: Toured): boolean {
  return MAIN_TOURS.includes(item.tour.toUpperCase())
}

/** A parlay with any non-main-tour leg goes to the Challenger section. */
export function splitByTour<S extends Toured, P extends { legs: Toured[] }>(
  data: { singles: S[]; parlays: P[] },
): TourSplit<S, P> {
  return {
    mainSingles: data.singles.filter(isMainTour),
    challSingles: data.singles.filter((p) => !isMainTour(p)),
    mainParlays: data.parlays.filter((p) => p.legs.every(isMainTour)),
    challParlays: data.parlays.filter((p) => p.legs.some((l) => !isMainTour(l))),
  }
}
