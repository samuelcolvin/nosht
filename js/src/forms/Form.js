import React from 'react'
import {Button, ButtonGroup, Form as BootstrapForm} from 'reactstrap'
import requests from '../requests'
import AsModal from '../general/Modal'
import Input from './Input'

export class Form extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      disabled: false,
      form_data: {},
      errors: {},
      form_error: null,
    }
    this.set_form_data = this.set_form_data.bind(this)
  }

  async submit (e) {
    e.preventDefault()
    if (Object.keys(this.state.form_data).length === 0) {
      this.setState({form_error: 'No data entered'})
      return
    }
    this.setState({disabled: true, errors: {}, form_error: null})
    let r
    try {
      r = await requests.post(this.props.action, this.state.form_data, {expected_statuses: [200, 201, 400]})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (r._response_status === 400) {
      console.warn('form error', r)
      const errors = {}
      for (let e of (r.details || [])) {
        errors[e.loc[0]] = e.msg
      }
      this.setState({disabled: false, errors, form_error: Object.keys(errors).length ? 'Error occurred' : null})
    } else {
      this.props.update && this.props.update()
      this.props.success_msg && this.props.ctx.setMessage(this.props.success_msg)
      this.props.finished(r)
    }
  }

  set_form_data (name, value) {
    const form_data = Object.assign({}, this.state.form_data, {[name]: value})
    this.setState({form_data})
    this.props.onChange && this.props.onChange(form_data)
  }

  render () {
    const initial = this.props.initial || {}
    const get_value = field => {
      const v = this.state.form_data[field.name]
      return v === undefined ? initial[field.name] : v
    }
    return (
      <BootstrapForm onSubmit={this.submit.bind(this)} className="highlight-required">
        <div className={this.props.form_body_class}>
          <div className="form-error text-right">{this.state.form_error}</div>
          {(this.props.fields || []).map((field, i) => (
            <Input key={i}
                    field={field}
                    value={get_value(field)}
                    error={this.state.errors[field.name]}
                    disabled={this.state.disabled}
                    set_value={v => this.set_form_data(field.name, v)}/>
          ))}
        </div>
        <div className={this.props.form_footer_class || 'text-right'}>
          <ButtonGroup>
            <Button type="button" color="secondary" onClick={() => this.props.finished && this.props.finished()}>
              {this.props.cancel || 'Cancel'}
            </Button>
            <Button type="submit" color="primary">
              {this.props.save || 'Save'}
            </Button>
          </ButtonGroup>
        </div>
      </BootstrapForm>
    )
  }
}

export const ModalForm = AsModal(Form)
