import React from 'react'
import {Editor as DraftEditor, EditorState, RichUtils} from 'draft-js'
import {
  Buttons,
  LinkModal,
  decorator,
  from_markdown,
  to_markdown,
  getEntitySelectionState,
  looks_like_link
} from './utils'

export default class Editor extends React.Component {
  constructor (props) {
    super(props)

    let editorState = EditorState.createEmpty(decorator)
    let edit_raw = false
    let raw_content = ''
    if (window.sessionStorage.raw_md_editor === 'true') {
      edit_raw = true
      raw_content = this.props.value || ''
    } else if (this.props.value) {
      editorState = from_markdown(this.props.value)
    }

    this.state = {
      linkModal: false,
      editUrl: '',
      selectionState: {},
      editorState,
      edit_raw,
      raw_content,
    }

    this.onChange = this.onChange.bind(this)
    this.promptLink = this.promptLink.bind(this)
    this.updateLink = this.updateLink.bind(this)
    this.removeLink = this.removeLink.bind(this)
    this.applyInlineStyle = this.applyInlineStyle.bind(this)
    this.applyBlockStyle = this.applyBlockStyle.bind(this)
  }

  onChange (editorState) {
    const selection = editorState.getSelection()
    const content = editorState.getCurrentContent()
    const block = content.getBlockForKey(selection.getFocusKey())
    const block_type = block.getType()
    const selectionState = {
      bold: false,
      italic: false,
      underline: false,
      url: null,
      heading: ['header-one', 'header-two'].includes(block_type),
      list: block_type === 'unordered-list-item',
      blockquote: block_type === 'blockquote',
    }
    const [start, finish] = [selection.getStartOffset(), selection.getEndOffset()]
    for (const style of block.getCharacterList().slice(start - 1, finish + 1).map(c => c.getStyle())) {
      selectionState.bold = selectionState.bold || style.has('BOLD')
      selectionState.italic = selectionState.italic || style.has('ITALIC')
      selectionState.underline = selectionState.underline || style.has('UNDERLINE')
    }
    const entity_key = block.getEntityAt(selection.getFocusOffset())

    if (entity_key) {
      const data = content.getEntity(entity_key).getData()
      if (data.url) {
        selectionState.url = data.url
      }
    }
    this.setState({editorState, selectionState})
    this.props.onChange && this.props.onChange(to_markdown(editorState))
  }

  promptLink () {
    const selection = this.state.editorState.getSelection()
    if (!selection.isCollapsed()) {
      const contentState = this.state.editorState.getCurrentContent()
      const startKey = selection.getStartKey()
      const startOffset = selection.getStartOffset()
      const block = contentState.getBlockForKey(startKey)
      const linkKey = block.getEntityAt(startOffset)
      let editUrl = ''
      if (linkKey) {
        editUrl = contentState.getEntity(linkKey).getData().url
      } else {
        const endOffset = selection.getEndOffset()
        const text = block.getText().slice(startOffset, endOffset)
        if (looks_like_link(text)) {
          editUrl = text
        }
      }
      this.setState({linkModal: true, editUrl})
    }
  }

  updateLink () {
    const contentState = this.state.editorState.getCurrentContent()
    let url = this.state.editUrl
    if (!url.match(/^https?:\/\//)) {
      url = 'http://' + url
    }
    const contentStateWithEntity = contentState.createEntity('LINK', 'MUTABLE', {url: url})
    const entityKey = contentStateWithEntity.getLastCreatedEntityKey()
    const newEditorState = EditorState.set(this.state.editorState, {currentContent: contentStateWithEntity})
    this.setState({linkModal: false, editUrl: ''})
    this.onChange(RichUtils.toggleLink(newEditorState, newEditorState.getSelection(), entityKey))
  }

  removeLink () {
    let selection = this.state.editorState.getSelection()
    if (selection.isCollapsed()) {
      selection = getEntitySelectionState(this.state.editorState.getCurrentContent(), selection)
    }
    if (selection) {
      this.onChange(RichUtils.toggleLink(this.state.editorState, selection, null))
    }
  }

  handleKeyCommand (command, editorState) {
    const newState = RichUtils.handleKeyCommand(editorState, command)
    if (newState) {
      this.onChange(newState)
      return 'handled'
    } else if (command === 'secondary-cut') {
      this.promptLink()
      return 'handled'
    } else {
      return 'not-handled'
    }
  }

  applyInlineStyle (icon) {
    this.onChange(RichUtils.toggleInlineStyle(this.state.editorState, icon.toUpperCase()))
  }

  applyHeading () {
    const selection = this.state.editorState.getSelection()
    const block_type = this.state.editorState.getCurrentContent().getBlockForKey(selection.getFocusKey()).getType()
    const lookup = {'unstyled': 'header-one', 'header-one': 'header-two', 'header-two': 'unstyled'}
    this.onChange(RichUtils.toggleBlockType(this.state.editorState, lookup[block_type]))
  }

  applyBlockStyle (icon) {
    const lookup = {'list-ul': 'unordered-list-item', 'quote-right': 'blockquote'}
    this.onChange(RichUtils.toggleBlockType(this.state.editorState, lookup[icon]))
  }

  setRaw () {
    const edit_raw = !this.state.edit_raw
    window.sessionStorage.raw_md_editor = edit_raw.toString()
    const state_change = {edit_raw}
    if (edit_raw) {
      state_change.raw_content = to_markdown(this.state.editorState)
    } else {
      state_change.editorState = from_markdown(this.state.raw_content)
    }
    this.setState(state_change)
  }

  onRawChange (e) {
    const md = e.target.value
    this.setState({raw_content: md})
    this.props.onChange && this.props.onChange(md)
  }

  render () {
    const ss = this.state.selectionState
    const buttons = [
      {icon: 'bold', onClick: this.applyInlineStyle, highlight: ss.bold},
      {icon: 'italic', onClick: this.applyInlineStyle, highlight: ss.italic},
      {icon: 'underline', onClick: this.applyInlineStyle, highlight: ss.underline},
      {icon: 'heading', onClick: this.applyHeading.bind(this), highlight: ss.heading},
      {icon: 'list-ul', onClick: this.applyBlockStyle, highlight: ss.list},
      {icon: 'quote-right', onClick: this.applyBlockStyle, highlight: ss.blockquote},
      {icon: 'link', title: 'convert selection to link', onClick: this.promptLink},
      {icon: 'unlink', title: 'remove link', onClick: this.removeLink},
      {icon: 'code', title: 'edit raw markdown', onClick: this.setRaw.bind(this), highlight: this.state.edit_raw},
    ]
    return (
      <div className={`editor py-2 ${this.props.invalid ? 'invalid' :''}`}>
        <LinkModal
          close={() => this.setState({linkModal: false, editUrl: ''})}
          isOpen={this.state.linkModal}
          url={this.state.editUrl}
          update={this.updateLink}
          onChange={e => this.setState({editUrl: e.target.value})}
        />
        <div className="d-flex justify-content-end">
          <Buttons buttons={buttons} edit_raw={this.state.edit_raw}/>
        </div>
        <div className="editor-wrapper p-2">
          <div onClick={() => this.refs.editor.focus()} className="editor-scroll">
            {
              this.state.edit_raw ?
                <textarea
                    value={this.state.raw_content}
                    ref="editor"
                    onChange={this.onRawChange.bind(this)}
                />
                :
                <DraftEditor
                    handleKeyCommand={this.handleKeyCommand.bind(this)}
                    editorState={this.state.editorState}
                    onChange={this.onChange}
                    placeholder={this.props.placeholder || 'Enter text...'}
                    ref="editor"
                    spellCheck={true}
                />
            }
          </div>
        </div>
        <div className="mx-1" style={{height: 22}}>
          {
            ss.url && (
              <small>
                <span className="text-muted mr-1">links to:</span>
                <a href={ss.url} target="_blank" rel="noopener noreferrer">{ss.url}</a>
              </small>
            )
          }
          {
            this.state.edit_raw && (
              <small>
                You're editing markdown, see&nbsp;
                <a href="https://guides.github.com/features/mastering-markdown/"
                   target="_blank" rel="noopener noreferrer">
                  here
                </a>
                &nbsp;for more details.
              </small>
            )
          }
        </div>
      </div>
    )
  }
}
