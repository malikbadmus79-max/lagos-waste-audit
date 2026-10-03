/**
 * Builds the resident survey on household waste collection in Lagos
 * (questionnaire v2, survey/questionnaire.md) as a Google Form and links
 * a Google Sheet that receives the responses.
 *
 * Run buildSurveyForm() once from script.google.com. The execution log
 * prints the public form link, the editor link and the response sheet link.
 *
 * Privacy settings: no email collection, no sign-in requirement, no free-text
 * fields for names, phone numbers or addresses.
 */

var LGAS = [
  'Agege', 'Ajeromi-Ifelodun', 'Alimosho', 'Amuwo-Odofin', 'Apapa',
  'Badagry', 'Epe', 'Eti-Osa', 'Ibeju-Lekki', 'Ifako-Ijaiye', 'Ikeja',
  'Ikorodu', 'Kosofe', 'Lagos Island', 'Lagos Mainland', 'Mushin', 'Ojo',
  'Oshodi-Isolo', 'Shomolu', 'Surulere', 'Not sure'
];

function buildSurveyForm() {
  var form = FormApp.create('Household Waste Collection in Lagos: Resident Survey');

  form.setDescription(
    'This short survey is part of an independent study of household waste ' +
    'collection in Lagos. It takes about 5 minutes. No names, phone numbers ' +
    'or house addresses are collected. Answers are reported only in summary ' +
    'form. Taking part is voluntary.'
  );
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setProgressBar(true);
  form.setConfirmationMessage(
    'Thank you. Your response has been recorded. Sharing the survey link ' +
    'with neighbours in other parts of Lagos helps the study cover every LGA.'
  );
  try { form.setRequireLogin(false); } catch (e) { /* option exists only for Workspace accounts */ }

  // Consent (page 1). "No" ends the form.
  var consent = form.addMultipleChoiceItem();
  consent.setTitle('0. I am 18 or older and agree to take part in this survey.')
    .setChoices([
      consent.createChoice('Yes', FormApp.PageNavigationType.CONTINUE),
      consent.createChoice('No', FormApp.PageNavigationType.SUBMIT)
    ])
    .setRequired(true);

  // Section A: Location
  form.addPageBreakItem().setTitle('Section A: Location');

  form.addListItem()
    .setTitle('1. Which Local Government Area (LGA) do you live in?')
    .setChoiceValues(LGAS)
    .setRequired(true);

  form.addTextItem()
    .setTitle('2. Which area or neighbourhood do you live in?')
    .setHelpText('Area name only, for example "Ikotun" or "Ojodu Berger". Do not enter a street address or house number.')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('3. Which best describes the road in front of your home?')
    .setChoiceValues([
      'Tarred, good condition',
      'Tarred but badly damaged',
      'Untarred (sand or laterite)',
      'Footpath only'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('4. Can a refuse truck drive up to your gate?')
    .setChoiceValues(['Yes', 'No', 'Not sure'])
    .setRequired(true);

  // Section B: Home
  form.addPageBreakItem().setTitle('Section B: Home');

  form.addMultipleChoiceItem()
    .setTitle('5. What type of home do you live in?')
    .setChoiceValues([
      'Room in a shared house (face-me-I-face-you)',
      'Self-contained or mini flat',
      'Flat with 2 or more bedrooms',
      'Duplex or detached house',
      'Other'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('6. Is your home inside a gated estate or close with a residents\' association?')
    .setChoiceValues(['Yes', 'No'])
    .setRequired(true);

  // Section C: Collection service
  form.addPageBreakItem().setTitle('Section C: Collection service');

  form.addMultipleChoiceItem()
    .setTitle('7. Who mainly collects your household waste?')
    .setChoiceValues([
      'PSP or LAWMA truck',
      'Cart pusher',
      'Estate or landlord arranges it',
      'Household burns or buries it',
      'Household dumps it (drain, roadside, open plot)',
      'Don\'t know'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('8. How often is the PSP or LAWMA truck supposed to collect your waste?')
    .setChoiceValues([
      'Weekly',
      'Every two weeks',
      'Monthly',
      'No fixed schedule',
      'Don\'t know',
      'Not applicable, we don\'t use the truck'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('9. In the last 4 weeks, how many times did the PSP or LAWMA truck actually collect your waste?')
    .setChoiceValues([
      '0', '1', '2', '3', '4', '5 or more',
      'Don\'t know',
      'Not applicable, we don\'t use the truck'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('10. When was your waste last collected (by anyone)?')
    .setChoiceValues([
      'Within the last 7 days',
      '8 to 14 days ago',
      '15 to 30 days ago',
      'More than a month ago',
      'Never collected',
      'Can\'t remember'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('11. When the truck does not come, what does your household usually do?')
    .setHelpText('Tick all that apply.')
    .setChoiceValues([
      'Wait for the next visit',
      'Call the PSP or LAWMA',
      'Pay a cart pusher',
      'Burn it',
      'Dump it',
      'Take it to a collection point',
      'Other'
    ])
    .setRequired(true);

  // Section D: Payment
  form.addPageBreakItem().setTitle('Section D: Payment');

  form.addMultipleChoiceItem()
    .setTitle('12. Does your household pay a waste bill?')
    .setChoiceValues([
      'Yes, regularly',
      'Yes, sometimes',
      'No',
      'Landlord or estate pays (included in rent or service charge)',
      'Don\'t know'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('13. Roughly how much does your household pay per month?')
    .setChoiceValues([
      'Nothing',
      'Under ₦1,000',
      '₦1,000 to ₦2,999',
      '₦3,000 to ₦4,999',
      '₦5,000 to ₦9,999',
      '₦10,000 or more',
      'Landlord or estate pays',
      'Don\'t know'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('14. If your household does not pay, or pays only sometimes, what are the main reasons?')
    .setHelpText('Tick all that apply.')
    .setChoiceValues([
      'Not applicable, we pay regularly',
      'Service is poor or irregular',
      'Cannot afford it',
      'Never received a bill',
      'Don\'t know who to pay',
      'Pay a cart pusher instead',
      'Other'
    ])
    .setRequired(true);

  // Section E: Overall
  form.addPageBreakItem().setTitle('Section E: Overall');

  form.addScaleItem()
    .setTitle('15. Overall, how satisfied are you with waste collection where you live?')
    .setBounds(1, 5)
    .setLabels('Very dissatisfied', 'Very satisfied')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('16. Is there anything else you would like to say about waste collection in your area?')
    .setHelpText('Optional. Please do not include names, phone numbers or addresses.')
    .setRequired(false);

  // Response spreadsheet
  var sheet = SpreadsheetApp.create('Lagos Waste Survey Responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  // Newer Forms versions create forms unpublished; publish where supported.
  try {
    if (typeof form.setPublished === 'function') { form.setPublished(true); }
  } catch (e) { /* publish manually from the form editor if this fails */ }

  Logger.log('Public form link: ' + form.getPublishedUrl());
  Logger.log('Editor link:      ' + form.getEditUrl());
  Logger.log('Response sheet:   ' + sheet.getUrl());
}
