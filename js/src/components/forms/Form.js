import React from 'react'
import {Button, Form as BootstrapForm, ModalBody, ModalFooter} from 'reactstrap'
import Input from './Input'
import AsModal from './Modal'

export default class Form extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      disabled: false,
      form_data: {},
      errors: {},
      form_error: null,
    }
    this.submit = this.submit.bind(this)
    this.set_form_data = this.set_form_data.bind(this)
  }

  async submit (e) {
    e.preventDefault()
    if (Object.keys(this.state.form_data).length === 0) {
      this.setState({form_error: 'No data entered'})
      return
    }
    this.setState({disabled: true, errors: {}, form_error: null})
    const method = this.props.mode === 'edit' ? this.props.requests.put : this.props.requests.post
    let r
    try {
      r = await method(this.props.action, this.state.form_data, {expected_statuses: [200, 201, 400]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    if (r._response_status === 400) {
      console.log('form error', r)
      const errors = {}
      for (let e of (r.details || [])) {
        errors[e.loc[0]] = e.msg
      }
      this.setState({disabled: false, errors, form_error: Object.keys(errors).length ? null : 'Error occurred'})
    } else {
      if (this.props.mode === 'edit') {
        this.props.set_message(`${this.props.page.singular} updated`)
        this.props.update && this.props.update()
      } else {
        this.props.set_message(`${this.props.page.singular} added`)
        if (this.props.go_to_new) {
          this.props.toggle_model(this.props.parent_uri + `${r.pk}/`)
          return
        }
      }
      this.props.toggle_model(this.props.parent_uri)
    }
  }

  set_form_data (name, value) {
    const form_data = Object.assign({}, this.state.form_data)
    form_data[name] = value
    this.setState({form_data})
  }

  render () {
    const initial = this.props.initial || {}
    const get_value = field => {
      const v = this.state.form_data[field.name]
      return v === undefined ? initial[field.name] : v
    }
    return (
      <BootstrapForm onSubmit={this.submit}>
        <ModalBody>
          <div className="form-error text-right">{this.state.form_error}</div>
          {(this.props.fields || []).map((field, i) => (
            <Input key={i}
                    field={field}
                    value={get_value(field)}
                    error={this.state.errors[field.name]}
                    disabled={this.state.disabled}
                    set_value={v => this.set_form_data(field.name, v)}/>
          ))}
        </ModalBody>
        <ModalFooter>
          <Button type="button" color="secondary" onClick={() => this.props.toggle_model()}>
            {this.props.cancel || 'Cancel'}
          </Button>
          <Button type="submit" color="primary">
            {this.props.save || 'Save'}
          </Button>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}

export const ModelForm = AsModal(Form)
