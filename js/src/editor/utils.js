import React from 'react'
import {
  Button,
  Modal, ModalHeader, ModalBody, ModalFooter,
  FormGroup, Input
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {CompositeDecorator, convertFromRaw, convertToRaw, EditorState, SelectionState} from 'draft-js'
import getRangesForDraftEntity from 'draft-js/lib/getRangesForDraftEntity'
import {mdToDraftjs, draftjsToMd} from 'draftjs-md-converter'

const find_link = (contentBlock, callback, contentState) => {
  contentBlock.findEntityRanges(
    character => {
      const entityKey = character.getEntity()
      return entityKey !== null && contentState.getEntity(entityKey).getType() === 'LINK'
    },
    callback
  )
}

const Link = (props) => (
  <span className="link-preview">
    {props.children}
  </span>
)

export const getEntitySelectionState = (contentState, selection) => {
  const block = contentState.getBlockForKey(selection.getAnchorKey())
  const selectionOffset = selection.getAnchorOffset()

  return getRangesForDraftEntity(block, block.getEntityAt(selectionOffset))
    // .filter(r => r.start <= selectionOffset && selectionOffset <= r.end)
    .map(range => new SelectionState({
      anchorOffset: range.start,
      anchorKey: block.getKey(),
      focusOffset: range.end,
      focusKey: block.getKey(),
      isBackward: false,
      hasFocus: selection.getHasFocus(),
    })
  )[0] || null
}

export const decorator = new CompositeDecorator([
  {
    strategy: find_link,
    component: Link,
  },
])

export const Buttons = ({buttons, edit_raw}) => (
  buttons.filter(b => b.icon === 'code' || !edit_raw).map(b => (
    <Button key={b.icon}
            color="link"
            title={b.disabled ? 'disabled' : b.title}
            className={b.highlight ? 'highlight' : ''}
            onMouseDown={e => {
              e.preventDefault()
              b.onClick(b.icon)
            }}
            onClick={e => e.preventDefault()}
            disabled={b.disabled}>
      <FontAwesomeIcon icon={b.icon}/>
    </Button>
  ))
)

export const LinkModal = ({close, isOpen, url, update, onChange}) => {
  return (
    <Modal isOpen={isOpen} toggle={close}>
      <ModalHeader toggle={close}>Insert Link</ModalHeader>
      <ModalBody>
        <FormGroup>
          <Input placeholder="www.example.com..." value={url} onChange={onChange}/>
        </FormGroup>
      </ModalBody>
      <ModalFooter>
        <Button color="secondary" onClick={close}>Close</Button>
        <Button color="primary" onClick={update}>Update</Button>
      </ModalFooter>
    </Modal>
  )
}

export const looks_like_link = s => (
  !s.match(/ /) && (
    s.match(/^(https?:|www\.)/) ||
    s.match(/\.(com|org|edu|gov|uk|net|ca|de|jr|fr|au|us|ru)($|\/)/)
  )
)

export const from_markdown = md => (
  EditorState.createWithContent(convertFromRaw(mdToDraftjs(md)), decorator)
)

const md_styles = {
  BOLD: '**',
}

export const to_markdown = state => (
  draftjsToMd(convertToRaw(state.getCurrentContent()), md_styles)
)
