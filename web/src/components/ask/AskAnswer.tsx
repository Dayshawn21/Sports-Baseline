import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import type { AnswerSegment } from '~/types/ask'
import { answerBlocks } from '~/utils/askAnswer'

function Segments({ segments, onNavigate }: { segments: AnswerSegment[]; onNavigate: () => void }) {
  return (
    <>
      {segments.map((segment, i) =>
        segment.kind === 'link' ? (
          <Link key={i} to={segment.path} onClick={onNavigate} className="ask-answer__link">
            {segment.text}
          </Link>
        ) : (
          <Fragment key={i}>{segment.text}</Fragment>
        ),
      )}
    </>
  )
}

/** The model's answer as paragraphs, lists and Lineform links only. */
export default function AskAnswer({ text, onNavigate }: { text: string; onNavigate: () => void }) {
  return (
    <div className="ask-answer">
      {answerBlocks(text).map((block, i) =>
        block.kind === 'paragraph' ? (
          <p key={i}>
            <Segments segments={block.segments} onNavigate={onNavigate} />
          </p>
        ) : (
          <ul key={i}>
            {block.items.map((item, j) => (
              <li key={j}>
                <Segments segments={item} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        ),
      )}
    </div>
  )
}
