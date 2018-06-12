import React from 'react'
import {Button, ModalBody, ModalFooter} from 'reactstrap'
import Dropzone from 'react-dropzone'
import AsModal from './Modal'

const file_key = f => `${f.name}-${f.size}`


class DropForm extends React.Component {
  constructor () {
    super()
    this.state = {}
    this.upload_file = this.upload_file.bind(this)
  }

  upload_file (key, file) {
    var formData = new FormData()
    formData.append('image', file)
    var xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/testing/', true)
    xhr.onload = event => this.setState({[key]: {status: 'complete', file: file}})
    xhr.onerror = () => console.error('file reading has failed')
    xhr.send(formData)
  }

  onDrop (accepted_files, refused_files) {
    const extra_state = {}
    const state_keys = Object.keys(this.state)
    for (let f of accepted_files) {
      const k = file_key(f)
      if (!state_keys.includes(k)) {
        extra_state[k] = {status: 'pending', file: f}
        this.upload_file(k, f)
      }
    }
    extra_state.files_refused = Boolean(refused_files.length)
    this.setState(extra_state)
  }

  render () {
    return [
      <ModalBody key="1">
        <Dropzone className="dropzone"
                  onDrop={this.onDrop.bind(this)}
                  accept={['image/jpeg', 'image/png']}
                  maxSize={10 * 1000 * 1000}
                  style={{}}>
          <p>Drop files here, or click to select files to upload.</p>
          <div className="previews">
            {Object.values(this.state).filter(item => item.file).map((item, i) => (
              <div key={i} className="file-preview">
                <img src={item.file.preview} alt={item.file.name} className="img-thumbnail"/>
                {item.file.name} {item.status}
              </div>
            ))}
          </div>
        </Dropzone>
        {this.state.files_refused && (
          <div className="form-error mt-1">
            Some files were refused for upload as they were not valid images.
          </div>
        )}
      </ModalBody>,
      <ModalFooter key="2">
        <Button type="button" color="secondary" onClick={() => this.props.toggle_model()}>
          {this.props.close || 'Close'}
        </Button>
      </ModalFooter>
    ]
  }
}

export const ModelDropForm = AsModal(DropForm)
