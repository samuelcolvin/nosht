import React from 'react'
import {Editor as DraftEditor, EditorState, RichUtils, convertToRaw} from 'draft-js'
import {draftToMarkdown} from 'markdown-draft-js'
import {Buttons, LinkModal, decorator, getEntitySelectionState} from './utils'

export default class Editor extends React.Component {
  constructor (props) {
    super(props)

    this.state = {
      editorState: EditorState.createEmpty(decorator),
      linkModal: false,
      editUrl: '',
      selectionState: {},
    }

    this.logState = () => {
      const content = this.state.editorState.getCurrentContent()
      console.log(convertToRaw(content))
      console.log(draftToMarkdown(convertToRaw(content)))
    }

    this.onChange = this.onChange.bind(this)
    this.promptLink = this.promptLink.bind(this)
    this.updateLink = this.updateLink.bind(this)
    this.removeLink = this.removeLink.bind(this)
    this.onBtnClick = this.onBtnClick.bind(this)
  }

  onChange (editorState) {
    const selection = editorState.getSelection()
    const content = editorState.getCurrentContent()
    const block = content.getBlockForKey(selection.getFocusKey())
    const selectionState = {
      bold: false,
      italic: false,
      underline: false,
      url: null
    }
    const [start, finish] = [selection.getStartOffset(), selection.getEndOffset()]
    for (const style of block.getCharacterList().slice(start, finish + 1).map(c => c.getStyle())) {
      selectionState.bold = selectionState.bold || style.has('BOLD')
      selectionState.italic = selectionState.italic || style.has('ITALIC')
      selectionState.underline = selectionState.underline || style.has('UNDERLINE')
    }
    const entity_key = block.getEntityAt(selection.getFocusOffset())

    if (entity_key) {
      const data = content.getEntity(entity_key).getData()
      console.log(data)
      if (data.url) {
        selectionState.url = data.url
      }
    }
    console.log('styles:', selectionState)
    this.setState({editorState, selectionState})
  }

  promptLink () {
    const selection = this.state.editorState.getSelection()
    if (!selection.isCollapsed()) {
      const contentState = this.state.editorState.getCurrentContent()
      const startKey = selection.getStartKey()
      const startOffset = selection.getStartOffset()
      const linkKey = contentState.getBlockForKey(startKey).getEntityAt(startOffset)
      const editUrl = linkKey ? contentState.getEntity(linkKey).getData().url : ''
      this.setState({linkModal: true, editUrl})
    }
  }

  updateLink () {
    const contentState = this.state.editorState.getCurrentContent()
    const contentStateWithEntity = contentState.createEntity('LINK', 'MUTABLE', {url: this.state.editUrl})
    const entityKey = contentStateWithEntity.getLastCreatedEntityKey()
    const newEditorState = EditorState.set(this.state.editorState, {currentContent: contentStateWithEntity})
    this.setState({
      editorState: RichUtils.toggleLink(newEditorState, newEditorState.getSelection(), entityKey),
      linkModal: false, editUrl: '',
    })
  }

  removeLink () {
    let selection = this.state.editorState.getSelection()
    if (selection.isCollapsed()) {
      selection = getEntitySelectionState(this.state.editorState.getCurrentContent(), selection)
    }
    if (selection) {
      this.setState({editorState: RichUtils.toggleLink(this.state.editorState, selection, null)})
    }
  }

  handleKeyCommand (command, editorState) {
    const newState = RichUtils.handleKeyCommand(editorState, command)
    if (newState) {
      this.onChange(newState)
      return 'handled'
    } else {
      return 'not-handled'
    }
  }

  onBtnClick (icon) {
    const lookup = {
      'bold': 'BOLD',
      'italic': 'ITALIC',
      'underline': 'UNDERLINE',
    }
    this.onChange(RichUtils.toggleInlineStyle(this.state.editorState, lookup[icon]))
  }

  render () {
    const ss = this.state.selectionState
    const buttons = [
      {icon: 'bold', onClick: this.onBtnClick, highlight: ss.bold},
      {icon: 'italic', onClick: this.onBtnClick, highlight: ss.italic},
      {icon: 'underline', onClick: this.onBtnClick, highlight: ss.underline},
      {icon: 'link', title: 'convert selection to link', onClick: this.promptLink},
      {icon: 'unlink', title: 'remove link', onClick: this.removeLink},
    ]
    // toggle, isOpen, url, update
    return (
      <div className="editor py-2 px-1">
        <LinkModal
          close={() => this.setState({linkModal: false})}
          isOpen={this.state.linkModal}
          url={this.state.editUrl}
          update={this.updateLink}
          onChange={e => this.setState({editUrl: e.target.value})}
        />
        <div className="d-flex justify-content-end">
          <Buttons buttons={buttons}/>
        </div>
        <div onClick={() => this.refs.editor.focus()} className="editor-wrapper">
          <DraftEditor
            editorState={this.state.editorState}
            handleKeyCommand={this.handleKeyCommand.bind(this)}
            onChange={this.onChange}
            placeholder="Enter text..."
            ref="editor"
          />
        </div>
        <div className="mx-1" style={{height: 22}}>
          {
            ss.url && <small>
              <span className="text-muted">links to:</span> {ss.url}
            </small>
          }
        </div>
      </div>
    )
  }
}
