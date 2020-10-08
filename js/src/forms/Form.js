import React from 'react'
import {Button, ButtonGroup, Form as BootstrapForm} from 'reactstrap'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import Input from './Input'
import WithContext from '../utils/context'

class _Form extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      disabled: false,
      errors: {},
      form_error: null,
    }
    this.onFieldChange = this.onFieldChange.bind(this)
  }

  componentDidMount () {
    if (this.props.submit_initial && this.props.fields) {
      const form_data = {}
      for (const field of this.props.fields) {
        const initial = this.props.initial[field.name]
        if (initial) {
          form_data[field.name] = initial
        }
      }
      this.props.onChange(form_data)
    }
  }

  async submit (e) {
    e.preventDefault()
    if (Object.keys(this.props.form_data).length === 0 && !this.props.allow_empty_form) {
      this.setState({form_error: 'No data entered'})
      return
    }
    const initial = this.props.initial || {}
    const missing = (
      this.props.fields
      .filter(f => f.required && !initial[f.name] && !this.props.form_data[f.name])
      .map(f => f.name)
    )
    if (missing.length) {
      // required since editors don't use inputs so required won't be caught be the browser
      const errors = {}
      missing.forEach(f => {errors[f] = 'Field Required'})
      this.setState({
        form_error: 'Required fields are empty',
        errors: errors
      })
      return
    }
    this.setState({disabled: true, errors: {}, form_error: null})
    let r
    const data = Object.assign({}, this.props.form_data)
    try {
      r = await requests.post(this.props.action, data, {expected_statuses: [200, 201, 400, 409]})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (r._response_status >= 400) {
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

  onFieldChange (name, value) {
    let form_data = Object.assign({}, this.props.form_data, {[name]: value})
    this.props.onChange && this.props.onChange(form_data)
  }

  render () {
    const initial = this.props.initial || {}
    const get_value = field => {
      const v = this.props.form_data[field.name]
      return v === undefined ? initial[field.name] : v
    }
    return (
      <BootstrapForm onSubmit={this.submit.bind(this)} className="highlight-required">
        <div className={this.props.form_body_class}>
          {this.props.content_before}
          <div className="form-error text-right">{this.state.form_error}</div>
          {(this.props.fields || []).map((field, i) => (
            <Input key={i}
                    field={field}
                    value={get_value(field)}
                    error={this.state.errors[field.name]}
                    disabled={this.state.disabled}
                    onChange={v => this.onFieldChange(field.name, v)}/>
          ))}
        </div>
        <div className={this.props.form_footer_class || 'text-right'}>
          <ButtonGroup>
            <Button type="button"
                    color="secondary"
                    disabled={this.state.disabled}
                    onClick={() => this.props.finished && this.props.finished()}>
              {this.props.cancel || 'Cancel'}
            </Button>
            <Button type="submit" color={this.props.save_color || 'primary'} disabled={this.state.disabled}>
              {this.props.save || 'Save'}
            </Button>
          </ButtonGroup>
        </div>
      </BootstrapForm>
    )
  }
}
export const Form = WithContext(_Form)

export class StandaloneForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {form_data: {}}
  }

  render () {
    return <Form {...this.props} form_data={this.state.form_data} onChange={form_data => this.setState({form_data})}/>
  }
}
export const ModalForm = AsModal(StandaloneForm)
