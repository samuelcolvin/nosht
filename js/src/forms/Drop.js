import React from 'react'
import {Button, Progress} from 'reactstrap'
import Dropzone from 'react-dropzone'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {error_response} from '../utils/requests'
import AsModal from '../general/Modal'

const file_key = f => `${f.name}-${f.size}`
const failed_icon = 'minus-circle'


export class DropzoneForm extends React.Component {
  constructor () {
    super()
    this.state = {}
    this.upload_file = this.upload_file.bind(this)
    this.uploads = []
  }

  upload_file (key, file) {
    var formData = new FormData()
    formData.append('image', file)
    var xhr = new XMLHttpRequest()
    const url = this.props.action.replace(/^(\/)?/, '/api/')
    xhr.open('POST', url, true)
    const failed = (event, reason) => {
      // console.warn('uploading file failed', xhr, event)
      this.setState({[key]: {icon: failed_icon, message: reason || 'A problem occurred', file}})
    }
    xhr.onload = event => {
      if (xhr.status === 200) {
        this.setState({[key]: {progress: 100, icon: 'check', file}})
        this.props.update && this.props.update()
      } else if (xhr.status === 413) {
        failed(event, 'Image too large')
      } else {
        const response_data = error_response(xhr)
        failed(event, response_data.message)
      }
    }
    xhr.onerror = failed
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) {
        this.setState({[key]: {
          // 90 not 100 so progress only completes when the request finishs
          progress: e.loaded / e.total * 90,
          file,
        }})
      }
    }
    xhr.send(formData)
    this.uploads.push(xhr)
  }

  onDropMultiple (accepted_files, refused_files) {
    const extra_state = {already_uploaded: false}
    for (let file of accepted_files) {
      const k = file_key(file)
      if (Object.keys(this.state).includes(k)) {
        extra_state.already_uploaded = true
      } else {
        extra_state[k] = {file}
        this.upload_file(k, file)
      }
    }
    for (let file of refused_files) {
      extra_state[file_key(file)] = {file, icon: failed_icon, message: 'Not a valid image'}
    }
    this.setState(extra_state)
  }

  onDropSingle (accepted_files, refused_files) {
    const extra_state = {}
    for (let file of accepted_files) {
      extra_state.file = {file}
      this.upload_file('file', file)
      break
    }
    for (let file of refused_files) {
      extra_state[file_key(file)] = {file, icon: failed_icon, message: 'Not a valid image'}
    }
    this.setState(extra_state)
  }

  componentWillUnmount () {
    for (let xhr of this.uploads) {
      xhr.abort()
    }
  }

  render () {
    return [
      <div key="1" className={this.props.form_body_class}>
        <Dropzone className="dropzone"
                  onDrop={this.props.multiple ? this.onDropMultiple.bind(this): this.onDropSingle.bind(this)}
                  accept={['image/jpeg', 'image/png']}
                  maxSize={10 * 1000 * 1000}>
          {
            this.props.multiple ?
            <p>Drop images here, or click to select images to upload.</p> :
            <p>Drop an image here, or click to select an image to upload.</p>
          }
          <p className="small">{this.props.help_text || 'Images must be at least 1920px x 500px.'}</p>
          <div className="previews">
            {Object.values(this.state).filter(item => item.file).map((item, i) => (
              <div key={i} className="file-preview">
                <div>
                  <img src={item.file.preview} alt={item.file.name} className="img-thumbnail"/>
                </div>
                <div>
                  {item.progress && <Progress value={item.progress} className="mt-1"/>}
                </div>
                {item.icon && <FontAwesomeIcon icon={item.icon} className="mt-1"/>}
                {item.message && <div className="mt-1">{item.message}</div>}
              </div>
            ))}
          </div>
        </Dropzone>
        {this.state.already_uploaded && (
          <small className="form-error mt-1">
            File already uploaded.
          </small>
        )}
      </div>,
      <div key="2" className={this.props.form_footer_class || 'text-right'}>
        <Button type="button" color="secondary" onClick={() => this.props.finished()}>
          {this.props.close || 'Close'}
        </Button>
      </div>
    ]
  }
}

export const ModalDropzoneForm = AsModal(DropzoneForm)
